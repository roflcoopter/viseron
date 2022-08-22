"""Logger constants."""

COMPONENT = "logger"

CONFIG_DEFAULT_LEVEL = "default_level"
CONFIG_LOGS = "logs"
CONFIG_CAMERAS = "cameras"

DEFAULT_LOG_LEVEL = "INFO"

VALID_LOG_LEVELS = {
    "CRITICAL": 50,
    "ERROR": 40,
    "WARNING": 30,
    "INFO": 20,
    "DEBUG": 10,
    "NOTSET": 0,
}
