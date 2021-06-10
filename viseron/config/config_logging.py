"""Logging config."""
from voluptuous import All, Any, Optional, Schema

LOG_LEVELS = Any("DEBUG", "INFO", "WARNING", "ERROR", "FATAL")


def upper_case(data: str) -> str:
    """Return data as upper case."""
    return data.upper()


SCHEMA = Schema(
    {
        Optional("level", default="INFO"): All(str, upper_case, LOG_LEVELS),
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
