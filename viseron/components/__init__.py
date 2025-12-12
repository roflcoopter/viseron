"""Viseron components."""

from __future__ import annotations

import importlib
import logging
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from inspect import signature
from timeit import default_timer as timer
from typing import TYPE_CHECKING, Any, Literal

import voluptuous as vol
from voluptuous.humanize import humanize_error

from viseron.const import (
    COMPONENT_RETRY_INTERVAL,
    COMPONENT_RETRY_INTERVAL_MAX,
    DOMAIN_FAILED,
    DOMAIN_IDENTIFIERS,
    DOMAIN_LOADED,
    DOMAIN_LOADING,
    DOMAIN_RETRY_INTERVAL,
    DOMAIN_RETRY_INTERVAL_MAX,
    DOMAIN_SETUP_TASKS,
    DOMAINS_TO_SETUP,
    EVENT_DOMAIN_SETUP_STATUS,
    FAILED,
    LOADED,
    LOADING,
    SLOW_DEPENDENCY_WARNING,
    SLOW_SETUP_WARNING,
    VISERON_SIGNAL_SHUTDOWN,
)
from viseron.events import EventData
from viseron.exceptions import ComponentNotReady, DomainNotReady
from viseron.helpers.storage import Storage

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains import OptionalDomain, RequireDomain
    from viseron.domains.camera import FailedCamera


@dataclass
class DomainToSetup:
    """Represent a domain to setup."""

    component: Component
    domain: str
    config: dict
    identifier: str
    require_domains: list[RequireDomain]
    optional_domains: list[OptionalDomain]
    error: str | None = None
    error_instance: FailedCamera | None = None
    retrying: bool = False

    def as_dict(self):
        """Return as dict."""
        return {
            "component": self.component.name,
            "domain": self.domain,
            "config": self.config,
            "identifier": self.identifier,
            "require_domains": self.require_domains,
            "optional_domains": self.optional_domains,
            "error": self.error,
        }


@dataclass
class EventDomanSetupStatusData(EventData, DomainToSetup):
    """Event with information on domain setup status."""


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

        self.domains_to_setup: list[DomainToSetup] = []

    def __str__(self) -> str:
        """Return string representation."""
        return self._name

    @property
    def name(self) -> str:
        """Return component name."""
        return self._name

    @property
    def path(self):
        """Return component path."""
        return self._path

    def get_component(self):
        """Return component module."""
        return importlib.import_module(self._path)

    def validate_component_config(self, component_module):
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
        slow_setup_warning = threading.Timer(
            SLOW_SETUP_WARNING,
            LOGGER.warning,
            (
                (
                    f"Setup of component {self.name} "
                    f"is taking longer than {SLOW_SETUP_WARNING} seconds"
                ),
            ),
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
                retry_timer = threading.Timer(
                    wait_time,
                    setup_component,
                    args=(self._vis, self),
                    kwargs={"tries": tries + 1},
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

        # Clear any domains that were marked for setup
        for domain_to_setup in self.domains_to_setup:
            del self._vis.data[DOMAINS_TO_SETUP][domain_to_setup.domain][
                domain_to_setup.identifier
            ]
        self.domains_to_setup.clear()
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
        require_domains: list[RequireDomain] | None,
        optional_domains: list[OptionalDomain] | None,
    ) -> None:
        """Add a domain to setup queue."""
        if (
            domain in self._vis.data[DOMAINS_TO_SETUP]
            and identifier in self._vis.data[DOMAINS_TO_SETUP][domain]
        ):
            LOGGER.warning(
                f"Domain {domain} with identifier {identifier} already in setup queue. "
                f"Skipping setup of domain {domain} with identifier {identifier} for "
                f"component {self.name}",
            )
            return

        domain_to_setup = DomainToSetup(
            component=self,
            domain=domain,
            config=config,
            identifier=identifier,
            require_domains=require_domains if require_domains else [],
            optional_domains=optional_domains if optional_domains else [],
        )
        self.domains_to_setup.append(domain_to_setup)
        self._vis.data[DOMAINS_TO_SETUP].setdefault(domain, {})[
            identifier
        ] = domain_to_setup

    def get_domain(self, domain):
        """Return domain module."""
        return importlib.import_module(f"{self._path}.{domain}")

    def validate_domain_config(
        self, config, domain, domain_module
    ) -> tuple[dict[str, Any], None] | tuple[None, str]:
        """Validate domain config."""
        if hasattr(domain_module, "CONFIG_SCHEMA"):
            try:
                return domain_module.CONFIG_SCHEMA(config), None
            except vol.Invalid as ex:
                error = (
                    f"Error validating config for domain {domain} and "
                    f"component {self.name}: "
                    f"{humanize_error(self._config, ex)}"
                )
                LOGGER.exception(error)
                return None, error
            except Exception:  # pylint: disable=broad-except
                error = f"Unknown error calling {self.name}.{domain} CONFIG_SCHEMA"
                LOGGER.exception(error)
                return None, error
        return config, None

    def _setup_dependencies(self, domain_to_setup: DomainToSetup) -> bool:
        """Await the setup of all dependencies."""

        def _slow_dependency_warning(futures) -> None:
            unfinished_dependencies = [future for future in futures if future.running()]
            if unfinished_dependencies:
                LOGGER.warning(
                    "Domain %s for component %s%s "
                    "is still waiting for dependencies: %s",
                    domain_to_setup.domain,
                    self.name,
                    (
                        f" with identifier {domain_to_setup.identifier}"
                        if domain_to_setup.identifier
                        else ""
                    ),
                    [
                        f"domain: {future.domain}, identifier: {future.identifier}"
                        for future in unfinished_dependencies
                    ],
                )

        dependencies_futures = [
            self._vis.data[DOMAIN_SETUP_TASKS][required_domain.domain][
                required_domain.identifier
            ]
            for required_domain in domain_to_setup.require_domains
        ]

        optional_dependencies_futures = [
            self._vis.data[DOMAIN_SETUP_TASKS][optional_domain.domain][
                optional_domain.identifier
            ]
            for optional_domain in domain_to_setup.optional_domains
            if (
                optional_domain.domain in self._vis.data[DOMAIN_IDENTIFIERS]
                and optional_domain.identifier
                in self._vis.data[DOMAIN_IDENTIFIERS][optional_domain.domain]
            )
        ]

        if dependencies_futures:
            LOGGER.debug(
                "Domain %s for component %s%s will wait for dependencies %s",
                domain_to_setup.domain,
                self.name,
                (
                    f" with identifier {domain_to_setup.identifier}"
                    if domain_to_setup.identifier
                    else ""
                ),
                [
                    f"domain: {future.domain}, identifier: {future.identifier}"
                    for future in dependencies_futures
                ],
            )
        if optional_dependencies_futures:
            LOGGER.debug(
                "Domain %s for component %s%s will wait for optional dependencies %s",
                domain_to_setup.domain,
                self.name,
                (
                    f" with identifier {domain_to_setup.identifier}"
                    if domain_to_setup.identifier
                    else ""
                ),
                [
                    f"domain: {future.domain}, identifier: {future.identifier}"
                    for future in optional_dependencies_futures
                ],
            )

        slow_dependency_warning = self._vis.background_scheduler.add_job(
            _slow_dependency_warning,
            "interval",
            seconds=SLOW_DEPENDENCY_WARNING,
            args=[dependencies_futures + optional_dependencies_futures],
        )
        failed = []
        for future in list(
            as_completed(dependencies_futures + optional_dependencies_futures)
        ):
            if future.result() is True:
                continue
            failed.append(future)
        try:
            slow_dependency_warning.remove()
        except Exception:  # pylint: disable=broad-except
            pass

        if failed:
            LOGGER.error(
                "Unable to setup dependencies for domain %s for component %s. "
                "Failed dependencies: %s",
                domain_to_setup.domain,
                self.name,
                [
                    f"domain: {future.domain}, "  # type: ignore[attr-defined]
                    f"identifier: {future.identifier}"
                    for future in failed
                ],
            )
            return False
        return True

    def setup_domain(self, domain_to_setup: DomainToSetup, tries=1):
        """Set up domain."""
        LOGGER.info(
            "Setting up domain %s for component %s%s%s",
            domain_to_setup.domain,
            self.name,
            (
                f" with identifier {domain_to_setup.identifier}"
                if domain_to_setup.identifier
                else ""
            ),
            (f", attempt {tries}" if tries > 1 else ""),
        )

        domain_setup_status(self._vis, domain_to_setup, DOMAIN_LOADING)

        domain_module = self.get_domain(domain_to_setup.domain)
        config, config_error = self.validate_domain_config(
            domain_to_setup.config, domain_to_setup.domain, domain_module
        )

        if not self._setup_dependencies(domain_to_setup):
            return False

        slow_setup_warning = threading.Timer(
            SLOW_SETUP_WARNING,
            LOGGER.warning,
            args=(
                (
                    "Setup of domain %s for component %s%s "
                    "is taking longer than %s seconds"
                ),
                domain_to_setup.domain,
                self.name,
                (
                    f" with identifier {domain_to_setup.identifier}"
                    if domain_to_setup.identifier
                    else ""
                ),
                SLOW_SETUP_WARNING,
            ),
        )

        start = timer()
        result: bool | Any = False
        if config:
            try:
                slow_setup_warning.start()
                sig = signature(domain_module.setup)
                if len(sig.parameters) == 4:
                    # If the setup function has an attempt parameter, we pass it
                    result = domain_module.setup(
                        self._vis, config, domain_to_setup.identifier, tries
                    )
                else:
                    result = domain_module.setup(
                        self._vis, config, domain_to_setup.identifier
                    )
            except DomainNotReady as error:
                if self._vis.shutdown_event.is_set():
                    LOGGER.warning(
                        f"Domain {domain_to_setup.domain} for "
                        f"component {self.name} setup aborted due to shutdown"
                    )
                    slow_setup_warning.cancel()
                    return False
                # Cancel the slow setup warning here since the retrying blocks
                domain_to_setup.error = str(error)
                domain_to_setup.retrying = True
                domain_setup_status(self._vis, domain_to_setup, DOMAIN_FAILED)
                slow_setup_warning.cancel()
                wait_time = min(
                    tries * DOMAIN_RETRY_INTERVAL, DOMAIN_RETRY_INTERVAL_MAX
                )
                LOGGER.error(
                    f"Domain {domain_to_setup.domain} "
                    f"for component {self.name} is not ready. "
                    f"Retrying in {wait_time} seconds. "
                    f"Error: {str(error)}"
                )
                elapsed = 0.0
                interval = 0.2
                while elapsed < wait_time:
                    if self._vis.shutdown_event.is_set():
                        LOGGER.warning("Domain setup retry aborted due to shutdown")
                        return False
                    time.sleep(interval)
                    elapsed += interval
                # Running with ThreadPoolExecutor and awaiting the future does not
                # cause a max recursion error if we retry for a long time
                with ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="Component.setup_domain"
                ) as executor:
                    future = executor.submit(
                        self.setup_domain,
                        domain_to_setup,
                        tries=tries + 1,
                    )
                    return future.result()
            except Exception as error:  # pylint: disable=broad-except
                LOGGER.exception(
                    f"Uncaught exception setting up domain {domain_to_setup.domain} for"
                    f" component {self.name}: {error}"
                )
                domain_to_setup.error = str(error)
                try:
                    self._vis.data[DOMAIN_IDENTIFIERS][domain_to_setup.domain].remove(
                        domain_to_setup.identifier
                    )
                except KeyError:
                    pass
            finally:
                slow_setup_warning.cancel()
        else:
            domain_to_setup.error = config_error

        end = timer()

        if result is True:
            LOGGER.info(
                "Setup of domain %s for component %s%s took %.1f seconds",
                domain_to_setup.domain,
                self.name,
                (
                    f" with identifier {domain_to_setup.identifier}"
                    if domain_to_setup.identifier
                    else ""
                ),
                end - start,
            )
            domain_setup_status(self._vis, domain_to_setup, DOMAIN_LOADED)
            return True

        if result is False:
            LOGGER.error(
                "Setup of domain %s for component %s%s failed",
                domain_to_setup.domain,
                self.name,
                (
                    f" with identifier {domain_to_setup.identifier}"
                    if domain_to_setup.identifier
                    else ""
                ),
            )
            self._vis.data[DOMAIN_FAILED][domain_to_setup.identifier] = domain_to_setup
            self._vis.data[DOMAIN_LOADING].pop(domain_to_setup.domain, None)
            domain_setup_status(self._vis, domain_to_setup, DOMAIN_FAILED)
            return False

        LOGGER.error(
            "Setup of domain %s for component %s did not return boolean",
            domain_to_setup.domain,
            self.name,
        )
        domain_setup_status(self._vis, domain_to_setup, DOMAIN_FAILED)
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
            LOGGER.error(f"Failed setup of component {component.name}")
            vis.data[FAILED][component.name] = component
            del vis.data[LOADING][component.name]

    except ModuleNotFoundError as err:
        LOGGER.error(f"Failed to load component {component.name}: {err}")
        vis.data[FAILED][component.name] = component
        del vis.data[LOADING][component.name]


def domain_dependencies(vis: Viseron) -> None:
    """Check that domain dependencies are resolved."""
    domain_to_setup: DomainToSetup
    for domain in vis.data[DOMAINS_TO_SETUP]:
        for domain_to_setup in vis.data[DOMAINS_TO_SETUP][domain].values():
            if domain_to_setup.identifier:
                vis.data[DOMAIN_IDENTIFIERS].setdefault(
                    domain_to_setup.domain, []
                ).append(domain_to_setup.identifier)

    for domain in vis.data[DOMAINS_TO_SETUP]:
        for domain_to_setup in list(vis.data[DOMAINS_TO_SETUP][domain].values())[:]:
            if not domain_to_setup.require_domains:
                continue
            for require_domain in domain_to_setup.require_domains:
                if (
                    require_domain.domain in vis.data[DOMAIN_IDENTIFIERS]
                    and require_domain.identifier
                    in vis.data[DOMAIN_IDENTIFIERS][require_domain.domain]
                ):
                    continue
                error = (
                    f"Domain {domain_to_setup.domain} "
                    f"for component {domain_to_setup.component.name} "
                    f"requires domain {require_domain.domain} with "
                    f"identifier {require_domain.identifier} but it has not been setup"
                )
                LOGGER.error(error)
                domain_to_setup.error = error
                try:
                    domain_setup_status(vis, domain_to_setup, DOMAIN_FAILED)
                    domain_to_setup.component.domains_to_setup.remove(domain_to_setup)
                    del vis.data[DOMAINS_TO_SETUP][domain_to_setup.domain][
                        domain_to_setup.identifier
                    ]
                except ValueError:
                    LOGGER.debug(
                        f"Domain {domain_to_setup.domain} has already been removed",
                        exc_info=True,
                    )


def _setup_domain(
    vis: Viseron, executor: ThreadPoolExecutor, domain_to_setup: DomainToSetup
) -> None:
    with DOMAIN_SETUP_LOCK:
        future = executor.submit(
            domain_to_setup.component.setup_domain,
            domain_to_setup,
        )
        setattr(future, "domain", domain_to_setup.domain)
        setattr(future, "identifier", domain_to_setup.identifier)
        vis.data[DOMAIN_SETUP_TASKS].setdefault(domain_to_setup.domain, {})[
            domain_to_setup.identifier
        ] = future


def setup_domain(
    vis: Viseron, executor: ThreadPoolExecutor, domain_to_setup: DomainToSetup
) -> None:
    """Set up single domain and all its dependencies."""
    with DOMAIN_SETUP_LOCK:
        if domain_to_setup.identifier in vis.data[DOMAIN_SETUP_TASKS].get(
            domain_to_setup.domain, {}
        ):
            return

    for required_domain in domain_to_setup.require_domains:
        setup_domain(
            vis,
            executor,
            vis.data[DOMAINS_TO_SETUP][required_domain.domain][
                required_domain.identifier
            ],
        )

    for optional_domain in domain_to_setup.optional_domains:
        if (
            optional_domain.domain in vis.data[DOMAIN_IDENTIFIERS]
            and optional_domain.identifier
            in vis.data[DOMAIN_IDENTIFIERS][optional_domain.domain]
        ):
            setup_domain(
                vis,
                executor,
                vis.data[DOMAINS_TO_SETUP][optional_domain.domain][
                    optional_domain.identifier
                ],
            )

    _setup_domain(vis, executor, domain_to_setup)


def setup_domains(vis: Viseron) -> None:
    """Set up all domains."""
    # Check that all domain dependencies are resolved
    domain_dependencies(vis)

    with ThreadPoolExecutor(
        max_workers=100, thread_name_prefix="setup_domains"
    ) as executor:
        for domain in vis.data[DOMAINS_TO_SETUP]:
            for domain_to_setup in vis.data[DOMAINS_TO_SETUP][domain].values():
                setup_domain(vis, executor, domain_to_setup)

        for future in as_completed(
            [
                future
                for domain in vis.data[DOMAIN_SETUP_TASKS]
                for future in vis.data[DOMAIN_SETUP_TASKS][domain].values()
            ]
        ):
            # Await results so that any errors are raised
            future.result()


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
            threading.Thread(
                target=setup_component,
                args=(vis, get_component(vis, component, config)),
                name=f"{component}_setup",
                daemon=True,
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


def domain_setup_status(
    vis: Viseron,
    domain: DomainToSetup,
    status: Literal["domain_loading", "domain_loaded", "domain_failed"],
) -> None:
    """Set the status of a domain setup.

    Sends an event when a domains setup status changes.
    """

    def handle_failed_domain() -> None:
        """Handle failed domain setup.

        Domains can have a setup_failed function that is called when the domain setup
        fails. The error_instance attribute is stored on the DomainToSetup object and
        can be used to give access to partial functionality of the domain
        (eg the recorder of a camera).
        """
        domain_module = importlib.import_module(f"viseron.domains.{domain.domain}")
        if hasattr(domain_module, "setup_failed"):
            domain.error_instance = domain_module.setup_failed(vis, domain)

    vis.data[DOMAIN_LOADING].setdefault(domain.domain, {})
    vis.data[DOMAIN_LOADED].setdefault(domain.domain, {})
    vis.data[DOMAIN_FAILED].setdefault(domain.domain, {})

    if status == DOMAIN_LOADING:
        vis.data[DOMAIN_LOADING][domain.domain][domain.identifier] = domain
    elif status == DOMAIN_LOADED:
        vis.data[DOMAIN_LOADED][domain.domain][domain.identifier] = domain
        vis.data[DOMAIN_LOADING][domain.domain].pop(domain.identifier, None)
        vis.data[DOMAIN_FAILED][domain.domain].pop(domain.identifier, None)
    elif status == DOMAIN_FAILED:
        vis.data[DOMAIN_LOADING][domain.domain].pop(domain.identifier, None)
        vis.data[DOMAIN_FAILED][domain.domain][domain.identifier] = domain
        handle_failed_domain()
    else:
        raise ValueError(f"Invalid domain status: {status}")
    vis.dispatch_event(
        EVENT_DOMAIN_SETUP_STATUS.format(
            status=status, domain=domain.domain, identifier=domain.identifier
        ),
        EventDomanSetupStatusData(**domain.__dict__),
        store=False,
    )
