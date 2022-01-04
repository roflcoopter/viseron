"""Viseron components."""
import concurrent
import importlib
import logging
import threading
import time
import traceback

import voluptuous as vol

from viseron.const import (
    COMPONENT_RETRY_INTERVAL,
    DOMAIN_RETRY_INTERVAL,
    FAILED,
    LOADED,
    LOADING,
)
from viseron.exceptions import ComponentNotReady, DomainNotReady

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

LAST_STAGE_COMPONENTS = ["nvr"]

LOGGER = logging.getLogger(__name__)


class Component:
    """Represents a Viseron component."""

    def __init__(self, vis, path, name, config):
        self._vis = vis
        self._path = path
        self._name = name
        self._config = config

        self.domains_to_setup = []

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
                LOGGER.exception(f"Error setting up component {self.name}: {ex}")
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
                    self.setup_component,
                    kwargs={"tries": tries + 1},
                ).start()
            except Exception as ex:  # pylint: disable=broad-except
                LOGGER.error(
                    f"Uncaught exception setting up component {self.name}: {ex}\n"
                    f"{traceback.print_exc()}"
                )

        return False

    def add_domain_to_setup(self, domain, config):
        """Add a domain to setup queue."""
        self.domains_to_setup.append({"domain": domain, "config": config})

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
                    f"Error setting up domain {domain} for component {self.name}: {ex}"
                )
                return None
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception(
                    "Unknown error calling %s.%s CONFIG_SCHEMA", self.name, domain
                )
                return None
        return config

    def setup_domain(self, domain, config, tries=1):
        """Set up domain."""
        LOGGER.info(f"Setting up domain {domain} for component {self.name}")
        domain_module = self.get_domain(domain)
        config = self.validate_domain_config(config, domain, domain_module)

        if config:
            try:
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
                    args=(
                        domain,
                        config,
                    ),
                    kwargs={"tries": tries + 1},
                ).start()
            except Exception as ex:  # pylint: disable=broad-except
                LOGGER.exception(
                    f"Uncaught exception setting up domain {domain} for "
                    f"component {self.name}: {ex}"
                )
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


def setup_domains(vis):
    """Set up all domains."""
    setup_threads = []
    for component in vis.data[LOADED].values():
        for domain_to_setup in component.domains_to_setup:
            setup_threads.append(
                threading.Thread(
                    target=component.setup_domain,
                    args=(
                        domain_to_setup["domain"],
                        domain_to_setup["config"],
                    ),
                    name=f"{component}_setup_{domain_to_setup['domain']}",
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


def setup_components(vis, config):
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

    setup_domains(vis)

    # Setup NVRs last
    for component in LAST_STAGE_COMPONENTS:
        setup_component(vis, get_component(vis, component, config))
