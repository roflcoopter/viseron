from voluptuous import Optional, Required, Schema

from lib.config.config_logging import SCHEMA as LOGGING_SCHEMA

SCHEMA = Schema({Required("type"): str, Optional("logging"): LOGGING_SCHEMA,})
