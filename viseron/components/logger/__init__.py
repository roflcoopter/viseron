"""Logger component.

Inspired by Home Assistant logger.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

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
    PREVIOUS_CONFIG,
    VALID_LOG_LEVELS,
)

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.logger.logger_types import _LoggerViseronData

LOGGER = logging.getLogger(__name__)

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


def setup(vis: Viseron, config: dict[str, Any]) -> bool:
    """Set up the logger component."""
    logger_config = config[COMPONENT]

    if PREVIOUS_CONFIG in vis.data.get(COMPONENT, {}):
        # During reload, apply only the changes between the old and new config to avoid
        # resetting log levels unnecessarily and causing log spam.
        _apply_config_changes(vis, logger_config)
        return True

    vis.data[COMPONENT] = {}
    vis.data[COMPONENT][CONFIG_LOGS] = {}
    vis.data[COMPONENT][CONFIG_CAMERAS] = dict(logger_config.get(CONFIG_CAMERAS) or {})
    vis.data[COMPONENT][CONFIG_DEFAULT_LEVEL] = logger_config.get(
        CONFIG_DEFAULT_LEVEL, DEFAULT_LOG_LEVEL
    )

    logging.setLoggerClass(
        _get_logger_class(
            vis.data[COMPONENT][CONFIG_LOGS],
            vis.data[COMPONENT][CONFIG_CAMERAS],
        )
    )

    _set_log_level(
        logging.getLogger(""),
        vis.data[COMPONENT][CONFIG_DEFAULT_LEVEL],
    )

    if CONFIG_LOGS in logger_config:
        _set_log_levels(
            vis, logger_config[CONFIG_LOGS], vis.data[COMPONENT][CONFIG_CAMERAS]
        )

    return True


def unload(vis: Viseron) -> None:
    """Unload the logger component.

    The logger component is a special case because it is always loaded and its config
    affects the logging behavior of all other components, therefore it is never
    truly "unloaded". Instead, we just snapshot the current config to be able to diff
    on the next setup call and apply only the necessary changes.

    Does not reset any log levels to avoid a window where loggers are
    unfiltered between unload and setup.
    """
    vis.data[COMPONENT][PREVIOUS_CONFIG] = {
        CONFIG_DEFAULT_LEVEL: vis.data[COMPONENT][CONFIG_DEFAULT_LEVEL],
        CONFIG_LOGS: dict(vis.data[COMPONENT][CONFIG_LOGS]),
        CONFIG_CAMERAS: dict(vis.data[COMPONENT][CONFIG_CAMERAS]),
    }


def _apply_config_changes(vis: Viseron, new_config: _LoggerViseronData) -> None:
    """Apply only the changes between old and new logger config.

    Computes the delta and applies removals first, then additions/changes.
    Priority order: cameras > logs > default_level.
    """
    previous = vis.data[COMPONENT].pop(PREVIOUS_CONFIG)

    old_default = previous[CONFIG_DEFAULT_LEVEL]
    new_default = new_config.get(CONFIG_DEFAULT_LEVEL, DEFAULT_LOG_LEVEL)

    old_logs = previous[CONFIG_LOGS]
    new_logs = new_config.get(CONFIG_LOGS, {})

    old_cameras = previous[CONFIG_CAMERAS]
    new_cameras = dict(new_config.get(CONFIG_CAMERAS) or {})

    log_overrides = vis.data[COMPONENT][CONFIG_LOGS]
    camera_overrides = vis.data[COMPONENT][CONFIG_CAMERAS]

    # Apply default level change
    if new_default != old_default:
        LOGGER.debug(
            "Changing default log level from %s to %s", old_default, new_default
        )
        _set_log_level(logging.getLogger(""), new_default)
        vis.data[COMPONENT][CONFIG_DEFAULT_LEVEL] = new_default

    # Handle removed log overrides
    for name in set(old_logs) - set(new_logs):
        LOGGER.debug("Removing log override for %s", name)
        log_overrides.pop(name, None)
        # Reset unless covered by a camera override (which takes precedence)
        if not _matches_camera_override(name, new_cameras):
            logger = logging.getLogger(name)
            getattr(logger, "orig_setLevel", logger.setLevel)(logging.NOTSET)

    # Handle added/changed log overrides
    for name, level in new_logs.items():
        if name not in old_logs or old_logs[name] != level:
            LOGGER.debug("Setting log override for %s to %s", name, level)
            log_overrides[name] = level
            # Only apply if not covered by a camera override
            if not _matches_camera_override(name, new_cameras):
                _set_log_level(logging.getLogger(name), level)

    # Handle removed camera overrides
    for camera_id in set(old_cameras) - set(new_cameras):
        LOGGER.debug("Removing camera log override for %s", camera_id)
        camera_overrides.pop(camera_id, None)
        for logger in _get_loggers_for_camera(camera_id):
            # Fall back to log override if one exists, otherwise inherit
            if logger.name in new_logs:
                _set_log_level(logger, new_logs[logger.name])
            else:
                getattr(logger, "orig_setLevel", logger.setLevel)(logging.NOTSET)

    # Handle added/changed camera overrides
    for camera_id, level in new_cameras.items():
        if camera_id not in old_cameras or old_cameras[camera_id] != level:
            LOGGER.debug("Setting camera log override for %s to %s", camera_id, level)
            camera_overrides[camera_id] = level
            for logger in _get_loggers_for_camera(camera_id):
                _set_log_level(logger, level)


def _matches_camera_override(
    logger_name: str, camera_overrides: dict[str, str]
) -> bool:
    """Check if a logger name matches any camera override."""
    return any(piece in camera_overrides for piece in logger_name.split("."))


def _get_loggers_for_camera(camera_id: str) -> list[logging.Logger]:
    """Get all instantiated loggers that match a camera identifier.

    Matches loggers whose name contains the camera_id as a dot-separated piece.
    """
    loggers = []
    for name, logger in list(logging.Logger.manager.loggerDict.items()):
        if isinstance(logger, logging.Logger) and camera_id in name.split("."):
            loggers.append(logger)
    return loggers


def _set_log_levels(
    vis: Viseron,
    logpoints: dict[str, str],
    camera_overrides: dict[str, str],
) -> None:
    """Update the log overrides dict and set levels on the loggers."""
    vis.data[COMPONENT][CONFIG_LOGS].update(logpoints)
    for key, value in logpoints.items():
        # Only apply if not covered by a camera override (camera takes precedence)
        if not _matches_camera_override(key, camera_overrides):
            _set_log_level(logging.getLogger(key), value)


def _set_log_level(logger: logging.Logger, level: str) -> None:
    """Set log level, bypassing ViseronLogger.setLevel override."""
    getattr(logger, "orig_setLevel", logger.setLevel)(VALID_LOG_LEVELS[level])


def _get_logger_class(
    log_overrides: dict[str, str], camera_log_overrides: dict[str, str]
) -> type[logging.Logger]:
    """Create a logger subclass.

    Used to make sure overridden log levels are set properly.
    """

    class ViseronLogger(logging.Logger):
        """Logger with built in level overrides."""

        def __init__(self, name: str, level: int = logging.NOTSET) -> None:
            for piece in name.split("."):
                if piece in camera_log_overrides:
                    level = VALID_LOG_LEVELS[camera_log_overrides[piece]]
                    break

            super().__init__(name, level=level)

        def setLevel(self, level: int | str) -> None:  # noqa: N802
            """Set the log level unless overridden."""
            if self.name in log_overrides:
                return

            if _matches_camera_override(self.name, camera_log_overrides):
                return

            super().setLevel(level)

        # pylint: disable=invalid-name
        def orig_setLevel(self, level: int | str) -> None:  # noqa: N802
            """Set the log level."""
            super().setLevel(level)

    return ViseronLogger
