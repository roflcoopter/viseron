"""Viseron components."""

from __future__ import annotations

import importlib
import logging
import threading
import time
import traceback
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from inspect import signature
from timeit import default_timer as timer
from typing import TYPE_CHECKING, Any, Literal

import voluptuous as vol
from voluptuous.humanize import humanize_error

from viseron.const import (
    COMPONENT_RETRY_INTERVAL,
    COMPONENT_RETRY_INTERVAL_MAX,
    DOMAIN_RETRY_INTERVAL,
    DOMAIN_RETRY_INTERVAL_MAX,
    FAILED,
    LOADED,
    LOADING,
    SLOW_DEPENDENCY_WARNING,
    SLOW_SETUP_WARNING,
    VISERON_SIGNAL_SHUTDOWN,
)
from viseron.domain_registry import DomainEntry, DomainState
from viseron.exceptions import ComponentNotReady, DomainNotReady
from viseron.helpers.named_timer import NamedTimer
from viseron.helpers.storage import Storage
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains import OptionalDomain, RequireDomain


LOGGING_COMPONENTS = {"logger"}
# Core components are always loaded even if they are not present in config
CORE_COMPONENTS = {"data_stream"}
# Default components are always loaded even if they are not present in config
DEFAULT_COMPONENTS = {"webserver", "storage"}
# Critical components are required for Viseron to function properly
# If one of these components fail to load, Viseron will activate safe mode
CRITICAL_COMPONENTS = LOGGING_COMPONENTS | CORE_COMPONENTS | DEFAULT_COMPONENTS

DOMAIN_SETUP_LOCK = threading.Lock()

LOGGER = logging.getLogger(__name__)


class Component:
    """Represents a Viseron component."""

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

    def get_component(self):
        """Return component module."""
        return importlib.import_module(self._path)

    def validate_component_config(self, component_module) -> dict | bool | None:
        """Validate component config."""
        if hasattr(component_module, "CONFIG_SCHEMA"):
            try:
                return component_module.CONFIG_SCHEMA(self._config)
            except vol.Invalid as ex:
                LOGGER.exception(
                    f"Error validating config for component {self.name}: "
                    f"{humanize_error(self._config, ex)}"
                )
                return None
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unknown error calling %s CONFIG_SCHEMA", self.name)
                return None
        return True

    def setup_component(self, tries: int = 1) -> bool:
        """Set up component."""
        LOGGER.info(
            "Setting up component %s%s",
            self.name,
            (f", attempt {tries}" if tries > 1 else ""),
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
        config = self.validate_component_config(component_module)

        start = timer()
        result: bool | Any = False
        if config:
            try:
                slow_setup_warning.start()
                result = component_module.setup(self._vis, config)
            except ComponentNotReady as error:
                if self._vis.shutdown_event.is_set():
                    LOGGER.warning(
                        f"Component {self.name} setup aborted due to shutdown"
                    )
                    slow_setup_warning.cancel()
                    return False
                wait_time = min(
                    tries * COMPONENT_RETRY_INTERVAL, COMPONENT_RETRY_INTERVAL_MAX
                )
                LOGGER.error(
                    f"Component {self.name} is not ready. "
                    f"Retrying in {wait_time} seconds in the background. "
                    f"Error: {str(error)}"
                )
                retry_timer = NamedTimer(
                    wait_time,
                    setup_component,
                    args=(self._vis, self),
                    kwargs={"tries": tries + 1},
                    name=f"{self.name}_retry_timer",
                    daemon=True,
                )

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
            except Exception as ex:  # pylint: disable=broad-except
                LOGGER.error(
                    f"Uncaught exception setting up component {self.name}: {ex}\n"
                    f"{traceback.format_exc()}"
                )
            finally:
                slow_setup_warning.cancel()

        end = timer()
        if result is True:
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
        domain: str,
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
            LOGGER.warning(
                f"Domain {domain} with identifier {identifier} already in setup queue. "
                f"Skipping setup of domain {domain} with identifier {identifier} for "
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


def _wait_for_dependencies(
    vis: Viseron,
    entry: DomainEntry,
) -> bool:
    """Wait for all dependencies to complete setup."""
    registry = vis.domain_registry

    def _slow_warning(futures: list[Future]) -> None:
        running = [f for f in futures if f.running()]
        if running:
            LOGGER.warning(
                f"Domain {entry.domain} with identifier {entry.identifier} "
                "still waiting for dependencies",
            )

    # Collect futures for required domains
    futures: list[Future] = []
    for required in entry.require_domains:
        # Skip if already loaded
        if registry.is_loaded(required.domain, required.identifier):
            continue
        future = registry.get_future(required.domain, required.identifier)
        if future:
            futures.append(future)

    # Collect futures for optional domains
    for optional in entry.optional_domains:
        if not registry.is_configured(optional.domain, optional.identifier):
            continue
        if registry.is_loaded(optional.domain, optional.identifier):
            continue
        future = registry.get_future(optional.domain, optional.identifier)
        if future:
            futures.append(future)

    if not futures:
        return True

    LOGGER.debug(
        f"Domain {entry.domain} with identifier {entry.identifier} "
        f"waiting for {len(futures)} dependencies",
    )

    # Set up slow warning
    slow_warning_job = vis.background_scheduler.add_job(
        _slow_warning,
        "interval",
        seconds=SLOW_DEPENDENCY_WARNING,
        args=[futures],
    )

    # Wait for all dependencies
    failed = []
    for future in as_completed(futures):
        if future.result() is not True:
            failed.append(future)

    try:
        slow_warning_job.remove()
    except Exception:  # pylint: disable=broad-except
        pass

    if failed:
        LOGGER.error(
            f"Unable to setup dependencies for domain {entry.domain} "
            f"with identifier {entry.identifier} "
            f"for component {entry.component_name}"
        )
        return False
    return True


def _setup_single_domain(vis: Viseron, entry: DomainEntry, tries: int = 1) -> bool:
    """Set up a single domain."""
    registry = vis.domain_registry
    component_path = entry.component_path

    LOGGER.info(
        (
            f"Setting up domain {entry.domain} with identifier {entry.identifier} "
            f"for component {entry.component_name}"
        )
        + (f", attempt {tries}" if tries > 1 else "")
    )

    registry.set_state(entry.domain, entry.identifier, DomainState.LOADING)

    # Wait for dependencies
    if not _wait_for_dependencies(vis, entry):
        _handle_failed_domain(
            vis, entry, DomainState.FAILED, error="Dependencies failed"
        )
        return False

    # Load domain module
    try:
        domain_module = importlib.import_module(f"{component_path}.{entry.domain}")
    except ModuleNotFoundError as err:
        LOGGER.error(
            "Failed to load domain module " f"{component_path}.{entry.domain}: {err}"
        )
        _handle_failed_domain(vis, entry, DomainState.FAILED, error=str(err))
        return False

    # Validate config
    config = entry.config
    if hasattr(domain_module, "CONFIG_SCHEMA"):
        try:
            config = domain_module.CONFIG_SCHEMA(config)
        except vol.Invalid as ex:
            error = (
                f"Error validating config for domain {entry.domain} and "
                f"component {entry.component_name}: "
                f"{humanize_error(config, ex)}"
            )
            LOGGER.exception(error)
            _handle_failed_domain(vis, entry, DomainState.FAILED, error=error)
            return False
        except Exception:  # pylint: disable=broad-except
            error = (
                "Unknown error calling "
                f"{entry.component_name}.{entry.domain} CONFIG_SCHEMA"
            )
            LOGGER.exception(error)
            _handle_failed_domain(vis, entry, DomainState.FAILED, error=error)
            return False

    # Set up slow setup warning
    slow_setup_warning = NamedTimer(
        SLOW_SETUP_WARNING,
        LOGGER.warning,
        args=(
            f"Setup of domain {entry.domain} "
            f"with identifier {entry.identifier} "
            f"for component {entry.component_name} "
            f"is taking longer than {SLOW_SETUP_WARNING} seconds",
        ),
        name=f"{entry.domain}_{entry.identifier}_slow_setup_warning",
        daemon=True,
    )

    start = timer()
    result: bool | Any = False
    try:
        slow_setup_warning.start()
        sig = signature(domain_module.setup)
        if len(sig.parameters) == 4:
            # If the setup function has an attempt parameter, we pass it
            result = domain_module.setup(vis, config, entry.identifier, tries)
        else:
            result = domain_module.setup(vis, config, entry.identifier)
    except DomainNotReady as error:
        if vis.shutdown_event.is_set():
            LOGGER.warning(
                f"Domain {entry.domain} with identifier {entry.identifier} "
                f"for component {entry.component_name} "
                "setup aborted due to shutdown"
            )
            slow_setup_warning.cancel()
            return False

        _handle_failed_domain(vis, entry, DomainState.RETRYING, error=str(error))
        slow_setup_warning.cancel()

        wait_time = min(tries * DOMAIN_RETRY_INTERVAL, DOMAIN_RETRY_INTERVAL_MAX)
        LOGGER.error(
            f"Domain {entry.domain} "
            f"with identifier {entry.identifier} "
            f"for component {entry.component_name} is not ready. "
            f"Retrying in {wait_time} seconds. "
            f"Error: {str(error)}"
        )

        elapsed = 0.0
        interval = 0.2
        while elapsed < wait_time:
            if vis.shutdown_event.is_set():
                LOGGER.warning("Domain setup retry aborted due to shutdown")
                return False
            time.sleep(interval)
            elapsed += interval
        # Running with ThreadPoolExecutor and awaiting the future does not
        # cause a max recursion error if we retry for a long time
        with ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="Component.setup_domain"
        ) as executor:
            future = executor.submit(_setup_single_domain, vis, entry, tries + 1)
            return future.result()
    except Exception as error:  # pylint: disable=broad-except
        LOGGER.exception(
            f"Uncaught exception setting up domain {entry.domain} for"
            f" component {entry.component_name}: {error}"
        )
        _handle_failed_domain(vis, entry, DomainState.FAILED, error=str(error))
        return False
    finally:
        slow_setup_warning.cancel()

    end = timer()

    if result is True:
        LOGGER.info(
            f"Setup of domain {entry.domain} "
            f"with identifier {entry.identifier} "
            f"for component {entry.component_name} "
            f"took {end - start:.1f} seconds"
        )
        registry.set_state(entry.domain, entry.identifier, DomainState.LOADED)
        return True

    if result is False:
        LOGGER.error(
            f"Setup of domain {entry.domain} "
            f"with identifier {entry.identifier} "
            f"for component {entry.component_name} failed"
        )
        _handle_failed_domain(
            vis, entry, DomainState.FAILED, error="Setup returned False"
        )
        return False

    LOGGER.error(
        f"Setup of domain {entry.domain} "
        f"with identifier {entry.identifier} "
        f"for component {entry.component_name} did not return boolean"
    )
    _handle_failed_domain(
        vis, entry, DomainState.FAILED, error="Setup did not return boolean"
    )
    return False


def get_component(
    vis: Viseron,
    component: str,
    config: dict[str, Any],
) -> Component:
    """Get configured component."""
    from viseron import (  # pylint: disable=import-outside-toplevel,import-self
        components,
    )

    for _ in components.__path__:
        return Component(vis, f"{components.__name__}.{component}", component, config)

    raise ModuleNotFoundError(f"Component {component} not found")


def setup_component(vis: Viseron, component: Component, tries: int = 1) -> None:
    """Set up single component."""
    # When tries is larger than one, it means we are in a retry loop.
    if tries > 1:
        # Remove component from being marked as failed
        del vis.data[FAILED][component.name]

    try:
        vis.data[LOADING][component.name] = component
        if component.setup_component(tries=tries):
            vis.data[LOADED][component.name] = component
            del vis.data[LOADING][component.name]
        else:
            vis.data[FAILED][component.name] = component
            del vis.data[LOADING][component.name]

    except ModuleNotFoundError as err:
        LOGGER.error(f"Failed to load component {component.name}: {err}")
        vis.data[FAILED][component.name] = component
        del vis.data[LOADING][component.name]


def _submit_domain_setup(
    vis: Viseron,
    executor: ThreadPoolExecutor,
    entry: DomainEntry,
) -> None:
    """Submit a domain for setup in the executor."""
    registry = vis.domain_registry

    with DOMAIN_SETUP_LOCK:
        # Skip if already has a future
        if registry.get_future(entry.domain, entry.identifier):
            return

        future = executor.submit(_setup_single_domain, vis, entry)
        registry.set_future(entry.domain, entry.identifier, future)


def _schedule_domain_setup(
    vis: Viseron,
    executor: ThreadPoolExecutor,
    entry: DomainEntry,
) -> None:
    """Schedule a domain and its dependencies for setup."""
    registry = vis.domain_registry

    with DOMAIN_SETUP_LOCK:
        if registry.get_future(entry.domain, entry.identifier):
            return

    # Schedule required dependencies first
    for req in entry.require_domains:
        req_entry = registry.get(req.domain, req.identifier)
        if req_entry and req_entry.state == DomainState.PENDING:
            _schedule_domain_setup(vis, executor, req_entry)

    # Schedule optional dependencies
    for opt in entry.optional_domains:
        opt_entry = registry.get(opt.domain, opt.identifier)
        if opt_entry and opt_entry.state == DomainState.PENDING:
            _schedule_domain_setup(vis, executor, opt_entry)

    _submit_domain_setup(vis, executor, entry)


def setup_domains(vis: Viseron) -> None:
    """Set up all pending domains."""
    registry = vis.domain_registry

    entries_missing_deps = registry.validate_dependencies()
    for entry in entries_missing_deps:
        LOGGER.error(
            f"Domain {entry.domain} "
            f"with identifier {entry.identifier} "
            f"has missing dependencies: {entry.error}",
        )
        _handle_failed_domain(vis, entry, DomainState.FAILED, error=entry.error)

    pending = registry.get_pending()
    if not pending:
        return

    LOGGER.debug(f"Setting up {len(pending)} pending domains")

    with ThreadPoolExecutor(max_workers=100, thread_name_prefix="setup_domains") as ex:
        # Schedule all pending domains
        for entry in pending:
            _schedule_domain_setup(vis, ex, entry)

        # Wait for all to complete
        futures = [
            registry.get_future(e.domain, e.identifier)
            for e in pending
            if registry.get_future(e.domain, e.identifier)
        ]
        for future in as_completed(futures):  # type: ignore[arg-type]
            try:
                future.result()
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Domain setup raised exception")

    # Clear futures and handle failed domains
    for entry in pending:
        registry.clear_future(entry.domain, entry.identifier)


def _handle_failed_domain(
    vis: Viseron,
    entry: DomainEntry,
    state: Literal[DomainState.FAILED, DomainState.RETRYING],
    error: str | None = None,
) -> None:
    """Handle a failed domain setup."""
    error_instance = None
    try:
        domain_module = importlib.import_module(f"viseron.domains.{entry.domain}")
        if hasattr(domain_module, "setup_failed"):
            error_instance = domain_module.setup_failed(vis, entry)
    except Exception:  # pylint: disable=broad-except
        LOGGER.debug(
            f"No setup_failed handler for domain {entry.domain} "
            f"for component {entry.component_name}"
        )
    vis.domain_registry.set_state(
        entry.domain,
        entry.identifier,
        state,
        error_instance=error_instance,
        error=error,
    )


STORAGE_KEY = "critical_components_config"


class CriticalComponentsConfigStore:
    """Storage for critical components config.

    Used to store the last known good config for critical components.
    """

    def __init__(self, vis) -> None:
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


def setup_components(vis: Viseron, config: dict[str, Any]) -> None:
    """Set up configured components."""
    components_in_config = {key.split(" ")[0] for key in config}
    # Setup logger first
    for component in components_in_config & LOGGING_COMPONENTS:
        setup_component(vis, get_component(vis, component, config))

    # Setup core components
    for component in CORE_COMPONENTS:
        setup_component(vis, get_component(vis, component, config))

    # Small delay to ensure core components are fully initialized
    # before setting up default components (especially storage)
    time.sleep(0.5)

    # Setup default components
    for component in DEFAULT_COMPONENTS:
        setup_component(vis, get_component(vis, component, config))

    if vis.safe_mode:
        return

    # If any of the critical components failed to load, we activate safe mode
    if any(component in vis.data[FAILED] for component in CRITICAL_COMPONENTS):
        LOGGER.warning("Critical components failed to load. Activating safe mode")
        activate_safe_mode(vis)
        return

    # Setup components in parallel
    setup_threads = []
    for component in (
        components_in_config
        - set(LOGGING_COMPONENTS)
        - set(CORE_COMPONENTS)
        - set(DEFAULT_COMPONENTS)
    ):
        setup_threads.append(
            RestartableThread(
                target=setup_component,
                args=(vis, get_component(vis, component, config)),
                name=f"{component}_setup",
                daemon=True,
                register=False,
            )
        )
    for thread in setup_threads:
        thread.start()

    def join(thread) -> None:
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
