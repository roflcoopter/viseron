"""Viseron components."""

from __future__ import annotations

import dataclasses
import importlib
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from timeit import default_timer as timer
from typing import TYPE_CHECKING, Any, ClassVar

import voluptuous as vol
from voluptuous.humanize import humanize_error

from viseron.const import (
    COMPONENT_RETRY_INTERVAL,
    COMPONENT_RETRY_INTERVAL_MAX,
    CORE_COMPONENTS,
    CRITICAL_COMPONENTS,
    DEFAULT_COMPONENTS,
    EVENT_COMPONENT_SETUP_STATUS,
    FAILED,
    LOADED,
    LOADING,
    LOGGING_COMPONENTS,
    SLOW_SETUP_WARNING,
    VISERON_SIGNAL_SHUTDOWN,
)
from viseron.domain_registry import DomainEntry, DomainState
from viseron.domains import get_unload_order, unload_domain
from viseron.events import EventData
from viseron.exceptions import ComponentNotReady
from viseron.helpers.named_timer import NamedTimer
from viseron.helpers.storage import Storage
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from types import ModuleType

    from viseron import Viseron
    from viseron.domains import OptionalDomain, RequireDomain
    from viseron.viseron_types import SupportedDomains


LOGGER = logging.getLogger(__name__)


class ComponentState(Enum):
    """State of a component in its lifecycle."""

    LOADING = "loading"
    LOADED = "loaded"
    FAILED = "failed"
    RETRYING = "retrying"


class ComponentErrorSource(Enum):
    """Source of a component error."""

    VALIDATION = "validation"
    SETUP = "setup"
    SETUP_DOMAINS = "setup_domains"
    DOMAIN = "domain"
    IMPORT = "import"


@dataclass
class ComponentError:
    """Structured error from component or domain setup."""

    source: ComponentErrorSource
    message: str
    timestamp: float = field(default_factory=time.time)
    component_name: str | None = None
    domain: str | None = None
    identifier: str | None = None


@dataclass
class EventComponentSetupStatusData(EventData):
    """Event data for component setup status changes."""

    component: str
    state: str
    error: str | None = None
    validation_error: str | None = None


@dataclass
class ValidationResult:
    """Result of a component config validation."""

    success: bool
    config: dict[str, Any] | None = None
    error: str | None = None


class Component:
    """Represents a Viseron component."""

    retry_timers: ClassVar[dict[str, NamedTimer]] = {}

    def __init__(
        self,
        vis: Viseron,
        path: str,
        name: str,
        config: dict[str, Any],
    ) -> None:
        self._vis = vis
        self._path = path
        self._name = name
        self._config = config
        self._state = ComponentState.LOADING
        self._errors: list[ComponentError] = []
        self._errors_lock = threading.Lock()
        self._validation_error: str | None = None

    @property
    def state(self) -> ComponentState:
        """Return component state."""
        return self._state

    @state.setter
    def state(self, value: ComponentState) -> None:
        """Set component state."""
        old_state = self._state
        self._state = value
        if old_state != value:
            self._dispatch_status_event()

    @property
    def validation_error(self) -> str | None:
        """Return validation error if any."""
        return self._validation_error

    @validation_error.setter
    def validation_error(self, value: str | None) -> None:
        """Set validation error and dispatch status event."""
        if self._validation_error == value:
            return

        self._validation_error = value
        self._dispatch_status_event()

    def _dispatch_status_event(self) -> None:
        """Dispatch component setup status event."""
        self._vis.dispatch_event(
            EVENT_COMPONENT_SETUP_STATUS.format(
                status=self._state.value,
                component=self._name,
            ),
            EventComponentSetupStatusData(
                component=self._name,
                state=self._state.value,
                error=self._errors[-1].message if self._errors else None,
                validation_error=self._validation_error,
            ),
            store=False,
        )

    @property
    def errors(self) -> list[ComponentError]:
        """Return list(copy) of errors."""
        with self._errors_lock:
            return list(self._errors)

    def add_error(
        self,
        source: ComponentErrorSource,
        message: str,
        domain: SupportedDomains | None = None,
        identifier: str | None = None,
    ) -> None:
        """Add a structured error to this component."""
        error = ComponentError(
            source=source,
            message=message,
            component_name=self._name,
            domain=domain,
            identifier=identifier,
        )
        with self._errors_lock:
            self._errors.append(error)

    def add_domain_error(
        self,
        message: str,
        domain: SupportedDomains,
        identifier: str,
    ) -> None:
        """Add a structured error with domain context to this component."""
        self.add_error(
            source=ComponentErrorSource.DOMAIN,
            message=message,
            domain=domain,
            identifier=identifier,
        )

    def clear_errors(self) -> None:
        """Clear all errors and validation error."""
        with self._errors_lock:
            self._errors.clear()
        self._validation_error = None

    def as_status_dict(self) -> dict[str, Any]:
        """Return component status as dict."""
        domains = [
            entry.as_dict()
            for entry in self._vis.domain_registry.get_by_component(self._name)
        ]
        return {
            "name": self._name,
            "state": self._state.value,
            "errors": [dataclasses.asdict(error) for error in self.errors],
            "validation_error": self._validation_error,
            "domains": domains,
        }

    def __str__(self) -> str:
        """Return string representation."""
        return self._name

    @property
    def name(self) -> str:
        """Return component name."""
        return self._name

    @property
    def path(self) -> str:
        """Return component path."""
        return self._path

    def get_component(self) -> ModuleType:
        """Return component module."""
        return importlib.import_module(self._path)

    def validate_component_config(self) -> ValidationResult:
        """Validate component config."""
        component_module = self.get_component()
        if hasattr(component_module, "CONFIG_SCHEMA"):
            try:
                return ValidationResult(
                    success=True, config=component_module.CONFIG_SCHEMA(self._config)
                )
            except vol.Invalid as ex:
                error_msg = humanize_error(self._config, ex)
                LOGGER.exception(
                    f"Error validating config for component {self.name}: {error_msg}"
                )
                self.add_error(ComponentErrorSource.VALIDATION, error_msg)
                return ValidationResult(success=False, error=error_msg)
            except Exception as ex:  # pylint: disable=broad-except
                LOGGER.exception("Unknown error calling %s CONFIG_SCHEMA", self.name)
                self.add_error(ComponentErrorSource.VALIDATION, str(ex))
                return ValidationResult(success=False, error=str(ex))

        return ValidationResult(success=True, config={})

    def setup_component(
        self, tries: int = 1, *, domains_only: bool = False
    ) -> bool | None:
        """Set up component."""
        LOGGER.info(
            "Setting up component %s%s%s",
            self.name,
            (f", attempt {tries}" if tries > 1 else ""),
            (" (domains only)" if domains_only else ""),
        )
        slow_setup_warning = NamedTimer(
            SLOW_SETUP_WARNING,
            LOGGER.warning,
            args=(
                (
                    f"Setup of component {self.name} "
                    f"is taking longer than {SLOW_SETUP_WARNING} seconds"
                ),
            ),
            name=f"{self.name}_slow_setup_warning",
            daemon=True,
        )

        component_module = self.get_component()
        validation_result = self.validate_component_config()
        config = validation_result.config

        start = timer()
        result: bool | Any = False
        if validation_result.success:
            try:
                slow_setup_warning.start()
                # setup() is optional for stateless components
                if hasattr(component_module, "setup") and not domains_only:
                    result = component_module.setup(self._vis, config)
                # No setup function, assume success if setup_domains exists
                elif hasattr(component_module, "setup_domains"):
                    result = True
                else:
                    LOGGER.error(
                        f"Component {self.name} has neither setup() nor setup_domains()"
                    )
            except ComponentNotReady as error:
                if self._vis.shutdown_event.is_set():
                    LOGGER.warning(
                        f"Component {self.name} setup aborted due to shutdown"
                    )
                    self.add_error(
                        ComponentErrorSource.SETUP,
                        f"Setup aborted due to shutdown: {error}",
                    )
                    self.state = ComponentState.FAILED
                    slow_setup_warning.cancel()
                    return False
                self.add_error(ComponentErrorSource.SETUP, str(error))
                self.state = ComponentState.RETRYING
                wait_time = min(
                    tries * COMPONENT_RETRY_INTERVAL, COMPONENT_RETRY_INTERVAL_MAX
                )
                LOGGER.error(
                    f"Component {self.name} is not ready. "
                    f"Retrying in {wait_time} seconds in the background. "
                    f"Error: {error!s}"
                )
                retry_timer = NamedTimer(
                    wait_time,
                    setup_component,
                    args=(self._vis, self),
                    kwargs={"tries": tries + 1},
                    name=f"{self.name}_retry_timer",
                    daemon=True,
                )
                self.retry_timers[self.name] = retry_timer

                def cancel_retry_timer() -> None:
                    """Cancel retry timer."""
                    LOGGER.debug(
                        "Cancelling retry timer for component %s and try number %s",
                        self.name,
                        tries,
                    )
                    retry_timer.cancel()

                self._vis.register_signal_handler(
                    VISERON_SIGNAL_SHUTDOWN, cancel_retry_timer
                )
                retry_timer.start()
                return None  # Signal retry-in-progress
            except Exception as ex:  # pylint: disable=broad-except
                LOGGER.exception(f"Uncaught exception setting up component {self.name}")
                self.add_error(ComponentErrorSource.SETUP, str(ex))
            finally:
                slow_setup_warning.cancel()

        end = timer()
        if result is True:
            # Call setup_domains if it exists to register domains
            if hasattr(component_module, "setup_domains"):
                try:
                    component_module.setup_domains(self._vis, config)
                except Exception as ex:  # pylint: disable=broad-except
                    LOGGER.exception(
                        f"Uncaught exception in setup_domains for component {self.name}"
                    )
                    self.add_error(ComponentErrorSource.SETUP_DOMAINS, str(ex))
                    self.state = ComponentState.FAILED
                    return False
            self.state = ComponentState.LOADED
            LOGGER.info(
                "Setup of component %s took %.1f seconds",
                self.name,
                end - start,
            )
            return True

        # Clear any domains that were registered by this component
        registry = self._vis.domain_registry
        for entry in registry.get_by_component(self.name):
            if entry.state == DomainState.PENDING:
                registry.unregister(entry.domain, entry.identifier)

        self.state = ComponentState.FAILED
        if result is False:
            LOGGER.error(
                "Setup of component %s failed",
                self.name,
            )
            return False

        LOGGER.error(
            "Setup of component %s did not return boolean",
            self.name,
        )
        return False

    def add_domain_to_setup(
        self,
        domain: SupportedDomains,
        config: dict[str, Any],
        identifier: str,
        require_domains: list[RequireDomain] | None = None,
        optional_domains: list[OptionalDomain] | None = None,
    ) -> DomainEntry | None:
        """Register a domain for setup."""
        registry = self._vis.domain_registry

        # Check if already registered (any state)
        existing = registry.get(domain, identifier)
        if existing:
            if existing.state == DomainState.PENDING:
                LOGGER.warning(
                    f"Domain {domain} with identifier {identifier} "
                    "already pending setup. "
                    f"Skipping setup of domain {domain} "
                    f"with identifier {identifier} for "
                    f"component {self.name}",
                )
            return None

        return registry.register(
            component_name=self.name,
            component_path=self._path,
            domain=domain,
            identifier=identifier,
            config=config,
            require_domains=require_domains,
            optional_domains=optional_domains,
        )


def get_component(
    vis: Viseron,
    component: str,
    config: dict[str, Any],
) -> Component:
    """Get configured component."""
    # pylint: disable-next=import-outside-toplevel,import-self
    from viseron import (  # noqa: PLC0415
        components,
    )

    for _ in components.__path__:
        return Component(vis, f"{components.__name__}.{component}", component, config)

    raise ModuleNotFoundError(f"Component {component} not found")


def setup_component(
    vis: Viseron, component: Component, tries: int = 1, *, domains_only: bool = False
) -> None:
    """Set up single component."""
    # When tries is larger than one, it means we are in a retry loop.
    if tries > 1:
        # Remove component from being marked as failed
        vis.data[FAILED].pop(component.name, None)
        vis.data[LOADING].pop(component.name, None)
        component.clear_errors()

    try:
        component.state = ComponentState.LOADING
        vis.data[LOADING][component.name] = component
        result = component.setup_component(tries=tries, domains_only=domains_only)
        if result is True:
            vis.data[LOADED][component.name] = component
            del vis.data[LOADING][component.name]
        elif result is None:
            # Retry in progress, keep component in loading state
            pass
        else:
            vis.data[FAILED][component.name] = component
            del vis.data[LOADING][component.name]

    except ModuleNotFoundError as err:
        LOGGER.error(f"Failed to load component {component.name}: {err}")
        component.add_error(ComponentErrorSource.IMPORT, str(err))
        component.state = ComponentState.FAILED
        vis.data[FAILED][component.name] = component
        del vis.data[LOADING][component.name]


def unload_component(vis: Viseron, component: str) -> set[str] | None:
    """Unload a component."""
    # Cancel any ComponentNotReady retries to allow reload
    if retry_timer := Component.retry_timers.pop(component, None):
        LOGGER.debug(f"Cancelling retry timer {retry_timer.name}")
        retry_timer.cancel()

    component_instance: Component | None = vis.data[LOADED].get(component, None)
    if component_instance is None:
        LOGGER.debug(f"Component {component} not found for unload")
        return None

    # Keep track of other components that are affected by this unload
    affected_components = set()
    # Unload any domains that were registered by this component
    domains_to_unload = vis.domain_registry.get_by_component(component)
    if domains_to_unload:
        LOGGER.debug(
            "Component %s has %d domains to unload: %s",
            component,
            len(domains_to_unload),
            [(e.domain, e.identifier) for e in domains_to_unload],
        )

        for entry in domains_to_unload:
            unload_order = get_unload_order(vis, entry.domain, entry.identifier)
            for e in unload_order:
                unload_domain(vis, e.domain, e.identifier)
                if e.component_name != component:
                    affected_components.add(e.component_name)

    # Unload component-level entities
    entity_owner = vis.states.entity_owner.get(component, None)
    if entity_owner:
        for entity_id in list(vis.states.get_entities().keys()):
            # Need to use copy since unload_entity mutates the array
            if entity_id in entity_owner.get("entities", []).copy():
                vis.states.unload_entity(entity_id)

    # Call component's unload method
    component_module = component_instance.get_component()
    if hasattr(component_module, "unload"):
        try:
            component_module.unload(vis)
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(f"Error unloading component {component}")
    else:
        LOGGER.debug(f"Component {component} has no unload method")

    del vis.data[LOADED][component]
    return affected_components


STORAGE_KEY = "critical_components_config"


class CriticalComponentsConfigStore:
    """Storage for critical components config.

    Used to store the last known good config for critical components.
    """

    def __init__(self, vis: Viseron) -> None:
        self._vis = vis
        self._store = Storage(vis, STORAGE_KEY)

    def load(self) -> dict[str, Any]:
        """Load config."""
        return self._store.load()

    def save(self, config: dict[str, Any]) -> None:
        """Save config.

        Extracts only the critical components from the config.
        """
        critical_components_config = {
            component: config[component]
            for component in CRITICAL_COMPONENTS
            if component in config
        }
        self._store.save(critical_components_config)


def activate_safe_mode(vis: Viseron) -> None:
    """Activate safe mode."""
    vis.safe_mode = True
    # Get the last known good config
    critical_components_config = vis.critical_components_config_store.load()
    if not critical_components_config:
        LOGGER.warning(
            "No last known good config for critical components found, "
            "running with default config"
        )
        critical_components_config = {}

    loaded_set = set(vis.data[LOADED])
    # Setup logger first
    for component in LOGGING_COMPONENTS - loaded_set:
        setup_component(vis, get_component(vis, component, critical_components_config))

    # Setup core components
    for component in CORE_COMPONENTS - loaded_set:
        setup_component(vis, get_component(vis, component, critical_components_config))

    # Setup default components
    for component in DEFAULT_COMPONENTS - loaded_set:
        setup_component(vis, get_component(vis, component, critical_components_config))


def setup_components(
    vis: Viseron,
    config: dict[str, Any],
    *,
    reloading: bool = False,
    domains_only: bool = False,
    components: set[str] | None = None,
) -> None:
    """Set up configured components."""
    if components is None:
        components_to_setup = {key.split(" ")[0] for key in config}
    else:
        components_to_setup = components

    # Setup logger first if present in config
    for component in components_to_setup & LOGGING_COMPONENTS:
        setup_component(vis, get_component(vis, component, config))

    # Setup core components
    if not reloading:
        for component in CORE_COMPONENTS:
            setup_component(vis, get_component(vis, component, config))

    # Setup all default components, even if they are not present in config.
    # When reloading, only setup default components that are being reloaded.
    for component in (
        DEFAULT_COMPONENTS
        if not reloading
        else components_to_setup & DEFAULT_COMPONENTS
    ):
        setup_component(vis, get_component(vis, component, config))

    if vis.safe_mode:
        return

    # If any of the critical components failed to load, we activate safe mode
    if any(component in vis.data[FAILED] for component in CRITICAL_COMPONENTS):
        LOGGER.warning("Critical components failed to load. Activating safe mode")
        activate_safe_mode(vis)
        return

    # Setup components in parallel
    setup_threads = [
        RestartableThread(
            target=setup_component,
            args=(vis, get_component(vis, component, config)),
            kwargs={"domains_only": domains_only},
            name=f"{component}_setup",
            daemon=True,
            register=False,
        )
        for component in (
            components_to_setup
            - set(LOGGING_COMPONENTS)
            - set(CORE_COMPONENTS)
            - set(DEFAULT_COMPONENTS)
        )
    ]
    for thread in setup_threads:
        thread.start()

    def join(thread: RestartableThread) -> None:
        thread.join(timeout=30)
        time.sleep(0.5)  # Wait for thread to exit properly
        if thread.is_alive():
            LOGGER.error(f"{thread.name} did not finish in time")

    with ThreadPoolExecutor(
        max_workers=100, thread_name_prefix="setup_components"
    ) as executor:
        setup_thread_future = {
            executor.submit(join, setup_thread): setup_thread
            for setup_thread in setup_threads
        }
        for future in as_completed(setup_thread_future):
            future.result()
