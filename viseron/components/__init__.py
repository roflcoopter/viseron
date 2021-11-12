"""Viseron components."""
import importlib
import logging
import threading

import voluptuous as vol

from viseron.const import FAILED, LOADED, LOADING

LOGGING_COMPONENTS = ["logger"]
CORE_COMPONENTS = ["data_stream"]
UNMIGRATED_COMPONENTS = [
    "cameras",
    "motion_detection",
    "object_detection",
    "recorder",
    "mqtt",
    "post_processors",
    "logging",
]

LAST_STAGE_COMPONENTS = ["nvr"]

LOGGER = logging.getLogger(__name__)


class Component:
    """Represents a Viseron component."""

    def __init__(self, vis, path, name):
        self._vis = vis
        self._path = path
        self._name = name

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

    def validate_component_config(self, config, component_module):
        """Validate component config."""
        if hasattr(component_module, "CONFIG_SCHEMA"):
            try:
                return component_module.CONFIG_SCHEMA(config)  # type: ignore
            except vol.Invalid as ex:
                LOGGER.exception(f"Error setting up component {self.name}: {ex}")
                return None
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unknown error calling %s CONFIG_SCHEMA", self.name)
                return None
        return True

    def setup_component(self, config):
        """Set up component."""
        component_module = self.get_component()
        config = self.validate_component_config(config, component_module)

        if config:
            try:
                return component_module.setup(self._vis, config)
            except Exception as ex:  # pylint: disable=broad-except
                LOGGER.error(
                    f"Uncaught exception setting up component {self.name}: {ex}"
                )

        return False

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

    def setup_domain(self, config, domain):
        """Set up domain."""
        domain_module = self.get_domain(domain)
        config = self.validate_domain_config(config, domain, domain_module)

        if config:
            try:
                return domain_module.setup(self._vis, config)
            except Exception as ex:  # pylint: disable=broad-except
                LOGGER.exception(
                    f"Uncaught exception setting up domain {domain} for "
                    f"component {self.name}: {ex}"
                )
        return False


def get_component(vis, component):
    """Get configured component."""
    from viseron import (  # pylint: disable=import-outside-toplevel,import-self
        components,
    )

    for _ in components.__path__:
        return Component(vis, f"{components.__name__}.{component}", component)


def setup_component(vis, component: Component, config):
    """Set up single component."""
    LOGGER.info(f"Setting up {component.name}")
    try:
        vis.data[LOADING][component.name] = component
        if component.setup_component(config):
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
        setup_component(vis, get_component(vis, component), config)

    # Setup core components
    for component in CORE_COMPONENTS:
        setup_component(vis, get_component(vis, component), config)

    # Setup components in parallel
    setup_threads = []
    for component in components_in_config:
        setup_threads.append(
            threading.Thread(
                target=setup_component,
                args=(vis, get_component(vis, component), config),
            )
        )
    for thread in setup_threads:
        thread.start()
    for thread in setup_threads:
        thread.join()

    # Setup NVRs last
    for component in LAST_STAGE_COMPONENTS:
        setup_component(vis, get_component(vis, component), config)
