"""Post processor config."""
from voluptuous import ALLOW_EXTRA, Optional, Schema

from .config_logging import SCHEMA as LOGGING_SCHEMA, LoggingConfig

SCHEMA = Schema(
    {
        Optional("logging"): LOGGING_SCHEMA,
    },
    extra=ALLOW_EXTRA,
)


class PostProcessorsConfig:
    """Post processors config."""

    schema = SCHEMA

    def __init__(self, post_processors):
        self._logging = None
        # Pop all known configuration options to save a dictionary
        # which only contains the post processors
        _post_processors = post_processors.copy()
        if _post_processors.get("logging", None):
            self._logging = LoggingConfig(_post_processors.pop("logging"))

        self._post_processors = _post_processors

    @property
    def post_processors(self) -> list:
        """Return all post processor configs."""
        return self._post_processors

    @property
    def logging(self) -> LoggingConfig:
        """Return logging config."""
        return self._logging
