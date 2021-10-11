"""Viseron components."""
import importlib
import logging

import voluptuous as vol

LOGGING_COMPONENTS = ["logger"]
UNMIGRATED_COMPONENTS = [
    "cameras",
    "motion_detection",
    "object_detection",
    "recorder",
    "mqtt",
    "post_processors",
    "logging",
]

LOGGER = logging.getLogger(__name__)


class Component:
    """Represents a Viseron component."""

    def __init__(self, vis, path, name):
        self._vis = vis
        self._path = path
        self._name = name

    def __repr__(self):
        """Return string representation."""
        return self._name

    def get_component(self):
        """Return component module."""
        LOGGER.info(self._path)
        return importlib.import_module(self._path)

    def setup_component(self, config):
        """Set up component."""
        component_module = self.get_component()
        config = self.validate_component_config(config, self._name, component_module)

        if config:
            component_module.setup(self._vis, config)

    @staticmethod
    def validate_component_config(config, component, component_module):
        """Validate component config."""
        if hasattr(component_module, "CONFIG_SCHEMA"):
            try:
                return component_module.CONFIG_SCHEMA(config)  # type: ignore
            except vol.Invalid as ex:
                LOGGER.exception(f"Error setting up component {component}: {ex}")
                return None
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unknown error calling %s CONFIG_SCHEMA", component)
                return None


def get_component(vis, component):
    """Get configured component."""
    from viseron import (  # pylint: disable=import-outside-toplevel,import-self
        components,
    )

    for _ in components.__path__:
        return Component(vis, f"{components.__name__}.{component}", component)


def setup_component(component: Component, config):
    """Set up single component."""
    LOGGER.info(f"Setting up {component}")
    try:
        component.setup_component(config)
    except ModuleNotFoundError as err:
        LOGGER.error(f"Failed to load component {component}: {err}")


def setup_components(vis, config):
    """Set up configured components."""
    components_in_config = {key.split(" ")[0] for key in config}
    components_in_config = (
        components_in_config - set(UNMIGRATED_COMPONENTS) - set(LOGGING_COMPONENTS)
    )

    components_to_setup = set()

    for component in components_in_config:
        components_to_setup.add(get_component(vis, component))

    # Setup logger first
    setup_component(get_component(vis, "logger"), config)

    for component in components_to_setup:
        LOGGER.info(f"Setting up {component}")
        try:
            component.setup_component(config)
        except ModuleNotFoundError as err:
            LOGGER.error(f"Failed to load component {component}: {err}")
            continue
