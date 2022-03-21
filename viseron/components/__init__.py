"""Viseron components."""
from __future__ import annotations

import concurrent
import importlib
import logging
import threading
import time
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, List

import voluptuous as vol
from voluptuous.humanize import humanize_error

from viseron.const import (
    DOMAIN_IDENTIFIERS,
    DOMAIN_RETRY_INTERVAL,
    DOMAIN_RETRY_INTERVAL_MAX,
    DOMAIN_SETUP_TASKS,
    DOMAINS_TO_SETUP,
    FAILED,
    LOADED,
    LOADING,
)
from viseron.exceptions import DomainNotReady

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains import OptionalDomain, RequireDomain


@dataclass
class DomainToSetup:
    """Represent a domain to setup."""

    component: Component
    domain: str
    config: dict
    identifier: str
    require_domains: List[RequireDomain]
    optional_domains: List[OptionalDomain]


LOGGING_COMPONENTS = ["logger"]
CORE_COMPONENTS = ["data_stream"]

DOMAIN_SETUP_LOCK = threading.Lock()

LOGGER = logging.getLogger(__name__)


class Component:
    """Represents a Viseron component."""

    def __init__(self, vis, path, name, config):
        self._vis = vis
        self._path = path
        self._name = name
        self._config = config

        self.domains_to_setup: List[DomainToSetup] = []

    def __str__(self):
        """Return string representation."""
        return self._name

    @property
    def name(self):
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
                return component_module.CONFIG_SCHEMA(self._config)  # type: ignore
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

    def setup_component(self):
        """Set up component."""
        component_module = self.get_component()
        config = self.validate_component_config(component_module)

        if config:
            try:
                return component_module.setup(self._vis, config)
            except Exception as ex:  # pylint: disable=broad-except
                LOGGER.error(
                    f"Uncaught exception setting up component {self.name}: {ex}\n"
                    f"{traceback.print_exc()}"
                )
        # Clear any domains that were marked for setup
        for domain_to_setup in self.domains_to_setup:
            del self._vis.data[DOMAINS_TO_SETUP][domain_to_setup.domain][
                domain_to_setup.identifier
            ]
        self.domains_to_setup.clear()

        return False

    def add_domain_to_setup(
        self, domain, config, identifier, require_domains, optional_domains
    ):
        """Add a domain to setup queue."""
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

    def validate_domain_config(self, config, domain, domain_module):
        """Validate domain config."""
        if hasattr(domain_module, "CONFIG_SCHEMA"):
            try:
                return domain_module.CONFIG_SCHEMA(config)  # type: ignore
            except vol.Invalid as ex:
                LOGGER.exception(
                    f"Error validating config for domain {domain} and "
                    f"component {self.name}: "
                    f"{humanize_error(self._config, ex)}"
                )
                return None
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception(
                    "Unknown error calling %s.%s CONFIG_SCHEMA", self.name, domain
                )
                return None
        return config

    def _setup_dependencies(self, domain_to_setup: DomainToSetup):
        """Await the setup of all dependencies."""
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

        failed = []
        for future in list(
            concurrent.futures.as_completed(
                dependencies_futures + optional_dependencies_futures
            )
        ):
            if not future.result():
                failed.append(future)

        if failed:
            LOGGER.error(
                "Unable to setup dependencies for domain %s for component %s. "
                "Failed dependencies: %s",
                domain_to_setup.domain,
                self.name,
                [
                    f"domain: {future.domain}, "  # type: ignore
                    f"identifier: {future.identifier}"  # type: ignore
                    for future in failed
                ],
            )
            return False
        return True

    def setup_domain(self, domain_to_setup: DomainToSetup, tries=1):
        """Set up domain."""
        LOGGER.info(
            "Setting up domain %s for component %s%s",
            domain_to_setup.domain,
            self.name,
            (
                f" with identifier {domain_to_setup.identifier}"
                if domain_to_setup.identifier
                else ""
            ),
        )
        domain_module = self.get_domain(domain_to_setup.domain)
        config = self.validate_domain_config(
            domain_to_setup.config, domain_to_setup.domain, domain_module
        )

        if not self._setup_dependencies(domain_to_setup):
            return False

        if config:
            try:
                if domain_to_setup.identifier:
                    return domain_module.setup(
                        self._vis, config, domain_to_setup.identifier
                    )
                return domain_module.setup(self._vis, config)
            except DomainNotReady as error:
                wait_time = min(
                    tries * DOMAIN_RETRY_INTERVAL, DOMAIN_RETRY_INTERVAL_MAX
                )
                LOGGER.error(
                    f"Domain {domain_to_setup.domain} "
                    f"for component {self.name} is not ready. "
                    f"Retrying in {wait_time} seconds. "
                    f"Error: {str(error)}"
                )
                time.sleep(wait_time)
                # Running with ThreadPoolExecutor and awaiting the future does not
                # cause a max recursion error if we retry for a long time
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        self.setup_domain,
                        domain_to_setup,
                        tries=tries + 1,
                    )
                    return future.result()
            except Exception as ex:  # pylint: disable=broad-except
                LOGGER.exception(
                    f"Uncaught exception setting up domain {domain_to_setup.domain} for"
                    f" component {self.name}: {ex}"
                )
                try:
                    self._vis.data[DOMAIN_IDENTIFIERS][domain_to_setup.domain].remove(
                        domain_to_setup.identifier
                    )
                except KeyError:
                    pass
        return False


def get_component(vis, component, config):
    """Get configured component."""
    from viseron import (  # pylint: disable=import-outside-toplevel,import-self
        components,
    )

    for _ in components.__path__:
        return Component(vis, f"{components.__name__}.{component}", component, config)


def setup_component(vis, component: Component):
    """Set up single component."""
    LOGGER.info(f"Setting up {component.name}")

    try:
        vis.data[LOADING][component.name] = component
        if component.setup_component():
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


def domain_dependencies(vis):
    """Check that domain dependencies are resolved."""
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
                LOGGER.error(
                    f"Domain {domain_to_setup.domain} "
                    f"for component {domain_to_setup.component.name} "
                    f"requires domain {require_domain.domain} with "
                    f"identifier {require_domain.identifier} but it has not been setup"
                )
                domain_to_setup.component.domains_to_setup.remove(domain_to_setup)
                del vis.data[DOMAINS_TO_SETUP][domain_to_setup.domain][
                    domain_to_setup.identifier
                ]


def _setup_domain(vis, executor, domain_to_setup: DomainToSetup):
    with DOMAIN_SETUP_LOCK:
        future = executor.submit(
            domain_to_setup.component.setup_domain,
            domain_to_setup,
        )
        future.domain = domain_to_setup.domain
        future.identifier = domain_to_setup.identifier
        vis.data[DOMAIN_SETUP_TASKS].setdefault(domain_to_setup.domain, {})[
            domain_to_setup.identifier
        ] = future


def setup_domain(vis, executor, domain_to_setup: DomainToSetup):
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


def setup_domains(vis):
    """Set up all domains."""
    domain_dependencies(vis)

    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        for domain in vis.data[DOMAINS_TO_SETUP]:
            for domain_to_setup in vis.data[DOMAINS_TO_SETUP][domain].values():
                setup_domain(vis, executor, domain_to_setup)

        for future in concurrent.futures.as_completed(
            [
                future
                for domain in vis.data[DOMAIN_SETUP_TASKS]
                for future in vis.data[DOMAIN_SETUP_TASKS][domain].values()
            ]
        ):
            # Await results so that any errors are raised
            future.result()


def setup_components(vis: Viseron, config):
    """Set up configured components."""
    components_in_config = {key.split(" ")[0] for key in config}
    components_in_config = (
        components_in_config - set(LOGGING_COMPONENTS) - set(CORE_COMPONENTS)
    )

    # Setup logger first
    for component in LOGGING_COMPONENTS:
        setup_component(vis, get_component(vis, component, config))

    # Setup core components
    for component in CORE_COMPONENTS:
        setup_component(vis, get_component(vis, component, config))

    # Setup components in parallel
    setup_threads = []
    for component in components_in_config:
        setup_threads.append(
            threading.Thread(
                target=setup_component,
                args=(vis, get_component(vis, component, config)),
                name=f"{component}_setup",
            )
        )
    for thread in setup_threads:
        thread.start()

    def join(thread):
        thread.join(timeout=30)
        time.sleep(0.5)  # Wait for thread to exit properly
        if thread.is_alive():
            LOGGER.error(f"{thread.name} did not finish in time")

    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        setup_thread_future = {
            executor.submit(join, setup_thread): setup_thread
            for setup_thread in setup_threads
        }
        for future in concurrent.futures.as_completed(setup_thread_future):
            future.result()

    setup_domains(vis)
