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
    """Base config class for all post processors."""

    schema = SCHEMA

    def __init__(self, post_processors):
        self._logging = None
        # Pop all known configuration options to save a dictionary
        # which only contains the post processors
        if post_processors.get("logging", None):
            self._logging = LoggingConfig(post_processors.pop("logging"))

        self._post_processors = post_processors

    @property
    def post_processors(self):
        """Return all post processor configs."""
        return self._post_processors

    @property
    def logging(self):
        """Return logging config."""
        return self._logging
