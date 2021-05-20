"""Logging config."""
from voluptuous import All, Any, Optional, Schema, Upper

LOG_LEVELS = Any("DEBUG", "INFO", "WARNING", "ERROR", "FATAL")


SCHEMA = Schema(
    {
        Optional("level", default="INFO"): All(Upper, LOG_LEVELS),
        Optional("color_log", default=True): bool,
    }
)


class LoggingConfig:
    """Logging config."""

    schema = SCHEMA

    def __init__(self, logging):
        self._level = logging["level"]
        self._color_log = logging["color_log"]

    @property
    def level(self):
        """Return log level."""
        return self._level

    @property
    def color_log(self):
        """Return if log should be colored."""
        return self._color_log
