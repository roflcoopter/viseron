"""Logger component.

Inspired by Home Assistant logger.
"""
import logging

import voluptuous as vol

from viseron.helpers.validators import CameraIdentifier, CoerceNoneToDict, Maybe

from .const import (
    COMPONENT,
    CONFIG_CAMERAS,
    CONFIG_DEFAULT_LEVEL,
    CONFIG_LOGS,
    DEFAULT_CAMERAS,
    DEFAULT_LOG_LEVEL,
    DESC_CAMERA_IDENTIFIER,
    DESC_CAMERAS,
    DESC_COMPONENT,
    DESC_DEFAULT_LEVEL,
    DESC_LOGGER_NAME,
    DESC_LOGS,
    VALID_LOG_LEVELS,
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): vol.Schema(
            {
                vol.Optional(
                    CONFIG_DEFAULT_LEVEL,
                    default=DEFAULT_LOG_LEVEL,
                    description=DESC_DEFAULT_LEVEL,
                ): vol.All(vol.Lower, vol.In(VALID_LOG_LEVELS)),
                vol.Optional(CONFIG_LOGS, description=DESC_LOGS): {
                    vol.Required(str, description=DESC_LOGGER_NAME): vol.All(
                        vol.Lower, vol.In(VALID_LOG_LEVELS)
                    )
                },
                vol.Optional(
                    CONFIG_CAMERAS, default=DEFAULT_CAMERAS, description=DESC_CAMERAS
                ): vol.All(
                    Maybe(
                        {
                            CameraIdentifier(
                                description=DESC_CAMERA_IDENTIFIER
                            ): vol.All(vol.Lower, vol.In(VALID_LOG_LEVELS))
                        },
                    ),
                    CoerceNoneToDict(),
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis, config) -> bool:
    """Set up the logger component."""
    vis.data[COMPONENT] = {}
    vis.data[COMPONENT][CONFIG_LOGS] = {}
    logging.setLoggerClass(
        _get_logger_class(
            vis.data[COMPONENT][CONFIG_LOGS], config[COMPONENT][CONFIG_CAMERAS]
        )
    )

    def set_default_log_level(level) -> None:
        """Set the default log level for components."""
        _set_log_level(logging.getLogger(""), level)

    def set_log_levels(logpoints) -> None:
        """Set the specified log levels."""
        vis.data[COMPONENT][CONFIG_LOGS].update(logpoints)
        for key, value in logpoints.items():
            _set_log_level(logging.getLogger(key), value)

    set_default_log_level(
        config[COMPONENT].get(CONFIG_DEFAULT_LEVEL, DEFAULT_LOG_LEVEL)
    )

    if CONFIG_LOGS in config[COMPONENT]:
        set_log_levels(config[COMPONENT][CONFIG_LOGS])

    return True


def _set_log_level(logger, level) -> None:
    """Set log level."""
    getattr(logger, "orig_setLevel", logger.setLevel)(VALID_LOG_LEVELS[level])


def _get_logger_class(log_overrides, camera_log_overrides):
    """Create a logger subclass.

    Used to make sure overridden log levels are set properly
    """

    class ViseronLogger(logging.Logger):
        """Logger with built in level overrides."""

        def __init__(self, name, level=logging.NOTSET) -> None:
            for piece in name.split("."):
                if piece in camera_log_overrides:
                    level = VALID_LOG_LEVELS[camera_log_overrides[piece]]
                    break

            super().__init__(name, level=level)

        def setLevel(self, level) -> None:
            """Set the log level unless overridden."""
            if self.name in log_overrides:
                return

            for piece in self.name.split("."):
                if piece in camera_log_overrides:
                    return

            super().setLevel(level)

        # pylint: disable=invalid-name
        def orig_setLevel(self, level) -> None:
            """Set the log level."""
            super().setLevel(level)

    return ViseronLogger
