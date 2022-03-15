"""Logger component.

Inspired by Home Assistant logger.
"""
import logging

import voluptuous as vol

from .const import COMPONENT, DEFAULT_LOG_LEVEL, VALID_LOG_LEVELS

CONFIG_DEFAULT_LEVEL = "default_level"
CONFIG_LOGS = "logs"

CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT: vol.Schema(
            {
                vol.Optional(CONFIG_DEFAULT_LEVEL, default=DEFAULT_LOG_LEVEL): vol.All(
                    vol.Upper, vol.In(VALID_LOG_LEVELS)
                ),
                vol.Optional(CONFIG_LOGS): vol.Schema(
                    {str: vol.All(vol.Upper, vol.In(VALID_LOG_LEVELS))}
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis, config):
    """Set up the logger component."""
    vis.data[COMPONENT] = {}
    vis.data[COMPONENT][CONFIG_LOGS] = {}
    logging.setLoggerClass(_get_logger_class(vis.data[COMPONENT][CONFIG_LOGS]))

    def set_default_log_level(level):
        """Set the default log level for components."""
        _set_log_level(logging.getLogger(""), level)

    def set_log_levels(logpoints):
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


def _set_log_level(logger, level):
    """Set log level."""
    getattr(logger, "orig_setLevel", logger.setLevel)(VALID_LOG_LEVELS[level])


def _get_logger_class(log_overrides):
    """Create a logger subclass.

    Used to make sure overridden log levels are set properly
    """

    class ViseronLogger(logging.Logger):
        """Logger with built in level overrides."""

        def setLevel(self, level) -> None:
            """Set the log level unless overridden."""
            if self.name in log_overrides:
                return

            super().setLevel(level)

        # pylint: disable=invalid-name
        def orig_setLevel(self, level) -> None:
            """Set the log level."""
            super().setLevel(level)

    return ViseronLogger
