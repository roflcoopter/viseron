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
    COMPONENT_RETRY_INTERVAL,
    DOMAIN_IDENTIFIERS,
    DOMAIN_RETRY_INTERVAL,
    FAILED,
    LOADED,
    LOADING,
)
from viseron.exceptions import ComponentNotReady, DomainNotReady

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains import RequireDomain


@dataclass
class DomainToSetup:
    """Represent a domain to setup."""

    domain: str
    config: dict
    identifier: str
    require_domains: List[RequireDomain]


LOGGING_COMPONENTS = ["logger"]
CORE_COMPONENTS = ["data_stream"]
UNMIGRATED_COMPONENTS = [
    "cameras",
    "motion_detection",
    "object_detection",
    "recorder",
    "post_processors",
    "logging",
]

LAST_STAGE_COMPONENTS: List[str] = []

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

    def setup_component(self, tries=1):
        """Set up component."""
        component_module = self.get_component()
        config = self.validate_component_config(component_module)

        if config:
            try:
                return component_module.setup(self._vis, config)
            except ComponentNotReady:
                wait_time = min(tries, 10) * COMPONENT_RETRY_INTERVAL
                LOGGER.error(
                    f"Component {self.name} is not ready. "
                    f"Retrying in {wait_time} seconds"
                )
                threading.Timer(
                    wait_time,
                    setup_component,
                    args=(self._vis, self),
                    kwargs={"tries": tries + 1},
                ).start()
            except Exception as ex:  # pylint: disable=broad-except
                LOGGER.error(
                    f"Uncaught exception setting up component {self.name}: {ex}\n"
                    f"{traceback.print_exc()}"
                )
        # Clear any domains that were marked for setup
        self.domains_to_setup.clear()

        return False

    def add_domain_to_setup(self, domain, config, identifier, require_domains):
        """Add a domain to setup queue."""
        self.domains_to_setup.append(
            DomainToSetup(
                domain=domain,
                config=config,
                identifier=identifier,
                require_domains=require_domains,
            )
        )

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

    def setup_domain(self, domain, config, identifier, tries=1):
        """Set up domain."""
        LOGGER.info(
            f"Setting up domain {domain} for component {self.name}"
            f"{(f' with identifier {identifier}') if identifier else ''}"
        )
        domain_module = self.get_domain(domain)
        config = self.validate_domain_config(config, domain, domain_module)

        if config:
            try:
                if identifier:
                    return domain_module.setup(self._vis, config, identifier)
                return domain_module.setup(self._vis, config)
            except DomainNotReady:
                wait_time = min(tries, 10) * DOMAIN_RETRY_INTERVAL
                LOGGER.error(
                    f"Domain {domain} for component {self.name} is not ready. "
                    f"Retrying in {wait_time} seconds"
                )
                threading.Timer(
                    wait_time,
                    self.setup_domain,
                    args=(domain, config, identifier),
                    kwargs={"tries": tries + 1},
                ).start()
            except Exception as ex:  # pylint: disable=broad-except
                LOGGER.exception(
                    f"Uncaught exception setting up domain {domain} for "
                    f"component {self.name}: {ex}"
                )
                try:
                    self._vis.data[DOMAIN_IDENTIFIERS][domain].remove(identifier)
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


def setup_component(vis, component: Component, tries=1):
    """Set up single component."""
    LOGGER.info(
        f"Setting up {component.name}{(f', attempt {tries}') if tries > 1 else ''}"
    )

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


def domain_dependencies(vis):
    """Check that domain dependencies are resolved."""
    component: Component
    for component in vis.data[LOADED].values():
        for domain_to_setup in component.domains_to_setup:
            if domain_to_setup.identifier:
                vis.data[DOMAIN_IDENTIFIERS].setdefault(
                    domain_to_setup.domain, []
                ).append(domain_to_setup.identifier)

    for component in vis.data[LOADED].values():
        for domain_to_setup in component.domains_to_setup[:]:
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
                    f"Domain {domain_to_setup.domain} for component {component.name} "
                    f"requires domain {require_domain.domain} with "
                    f"identifier {require_domain.identifier} but it has not been setup"
                )
                component.domains_to_setup.remove(domain_to_setup)


def setup_domains(vis):
    """Set up all domains."""
    setup_threads = []
    component: Component
    for component in vis.data[LOADED].values():
        for domain_to_setup in component.domains_to_setup:
            setup_threads.append(
                threading.Thread(
                    target=component.setup_domain,
                    args=(
                        domain_to_setup.domain,
                        domain_to_setup.config,
                        domain_to_setup.identifier,
                    ),
                    name=f"{component}_setup_{domain_to_setup.domain}",
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


def setup_components(vis: Viseron, config):
    """Set up configured components."""
    components_in_config = {key.split(" ")[0] for key in config}
    components_in_config = (
        components_in_config
        - set(UNMIGRATED_COMPONENTS)
        - set(LOGGING_COMPONENTS)
        - set(CORE_COMPONENTS)
        - set(LAST_STAGE_COMPONENTS)
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

    domain_dependencies(vis)
    setup_domains(vis)

    # Setup last stage components
    for component in LAST_STAGE_COMPONENTS:
        setup_component(vis, get_component(vis, component, config))
