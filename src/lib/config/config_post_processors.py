from voluptuous import (
    ALLOW_EXTRA,
    Optional,
    Schema,
)

from .config_logging import SCHEMA as LOGGING_SCHEMA
from .config_logging import LoggingConfig

SCHEMA = Schema({Optional("logging"): LOGGING_SCHEMA,}, extra=ALLOW_EXTRA,)


class PostProcessorConfig:
    schema = SCHEMA

    def __init__(self, post_processors):
        self._logging = None
        # Pop all known configuration options to save a dicttionary
        # which only contains the post processors
        if post_processors.get("logging", None):
            self._logging = LoggingConfig(post_processors.pop("logging"))

        self._post_processors = post_processors

    @property
    def post_processors(self):
        return self._post_processors

    @property
    def logging(self):
        return self._logging
