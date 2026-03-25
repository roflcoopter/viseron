"""Logger constants."""
from typing import Final

COMPONENT: Final = "logger"


# CONFIG_SCHEMA constants
CONFIG_DEFAULT_LEVEL = "default_level"
CONFIG_LOGS: Final = "logs"
CONFIG_CAMERAS = "cameras"

DEFAULT_LOG_LEVEL = "info"
DEFAULT_CAMERAS: Final = None

DESC_COMPONENT = "Logger configuration."
DESC_DEFAULT_LEVEL = "Set default level for all logs."
DESC_LOGS = (
    "Map of logger names and their log level. </br>"
    "<b>Takes precedence over <code>default_level</code> config option.</b>"
)
DESC_LOGGER_NAME = "Set log level for a specific logger name."
DESC_CAMERAS = (
    "Map of camera identifiers and their log level. </br>"
    "<b>Takes precedence over <code>logs</code> and "
    "<code>default_level</code> config options.</b>"
)
DESC_CAMERA_IDENTIFIER = (
    "Override level for all loggers that contain the given camera identifier."
)

VALID_LOG_LEVELS = {
    "critical": 50,
    "error": 40,
    "warning": 30,
    "info": 20,
    "debug": 10,
}
