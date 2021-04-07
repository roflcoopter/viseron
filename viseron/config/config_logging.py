"""Logging config."""
from voluptuous import All, Any, Optional, Schema

LOG_LEVELS = Any("DEBUG", "INFO", "WARNING", "ERROR", "FATAL")


def upper_case(data: str) -> str:
    """Return data as upper case."""
    return data.upper()


SCHEMA = Schema({Optional("level", default="INFO"): All(str, upper_case, LOG_LEVELS)})


class LoggingConfig:
    """Logging config."""

    schema = SCHEMA

    def __init__(self, logging):
        self._level = logging["level"]

    @property
    def level(self):
        """Return log level."""
        return self._level
