"""Webserver constants."""

from datetime import timedelta
from typing import Final

COMPONENT = "webserver"

PATH_STATIC = "/src/viseron/frontend/static"

WEBSERVER_STORAGE_KEY = "webserver"
AUTH_STORAGE_KEY = "auth"
ONBOARDING_STORAGE_KEY = "onboarding"

ACCESS_TOKEN_EXPIRATION = timedelta(minutes=30)

# CONFIG_SCHEMA constants
CONFIG_PORT = "port"
CONFIG_DEBUG = "debug"

DEFAULT_COMPONENT: Final = None
DEFAULT_PORT = 8888
DEFAULT_DEBUG = False

DESC_COMPONENT = "Webserver configuration."

DESC_PORT = "Port to run the webserver on."
DESC_DEBUG = (
    "Enable debug mode for the webserver. <b>WARNING: Dont have this enabled in"
    " production as it weakens security.</b>"
)

# Auth constants
CONFIG_AUTH = "auth"
CONFIG_SESSION_EXPIRY = "session_expiry"
CONFIG_DAYS = "days"
CONFIG_HOURS = "hours"
CONFIG_MINUTES = "minutes"

DEFAULT_SESSION_EXPIRY: Final = None

DESC_AUTH = "Authentication configuration."
DESC_SESSION_EXPIRY = (
    "Session expiry time. After this time the user will be logged out. By default the"
    " sessions are infinite."
)
DESC_DAYS = "Days to expire session."
DESC_HOURS = "Hours to expire session."
DESC_MINUTES = "Minutes to expire session."

# Websocket constants
TYPE_RESULT = "result"
TYPE_AUTH_OK = "auth_ok"
TYPE_AUTH_REQUIRED = "auth_required"
TYPE_AUTH_NOT_REQUIRED = "auth_not_required"
TYPE_AUTH_FAILED = "auth_failed"


# Websocket error codes
WS_ERROR_INVALID_JSON = "invalid_json"
WS_ERROR_INVALID_FORMAT = "invalid_format"
WS_ERROR_UNKNOWN_COMMAND = "uknown_command"
WS_ERROR_UNKNOWN_ERROR = "uknown_error"
WS_ERROR_OLD_COMMAND_ID = "old_command_id"
WS_ERROR_SAVE_CONFIG_FAILED = "save_config_failed"
WS_ERROR_NOT_FOUND = "not_found"
WS_ERROR_UNAUTHORIZED = "unauthorized"


# Viseron data constants
WEBSOCKET_COMMANDS = "websocket_commands"
WEBSOCKET_CONNECTIONS = "websocket_connections"
