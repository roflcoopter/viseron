"""Webserver constants."""


COMPONENT = "webserver"

PATH_STATIC = "/src/viseron/frontend/static"


# CONFIG_SCHEMA constants
CONFIG_PORT = "port"
CONFIG_DEBUG = "debug"

DEFAULT_COMPONENT = None
DEFAULT_PORT = 8888
DEFAULT_DEBUG = False

DESC_COMPONENT = "Webserver configuration."

DESC_PORT = "Port to run the webserver on."
DESC_DEBUG = "Enable debug mode for the webserver."

# Status code constants
STATUS_SUCCESS = 200
STATUS_ERROR_EXTERNAL = 400
STATUS_ERROR_ENDPOINT_NOT_FOUND = 404
STATUS_ERROR_METHOD_NOT_ALLOWED = 405
STATUS_ERROR_INTERNAL = 500


# Websocket constants
TYPE_RESULT = "result"


# Websocket error codes
WS_ERROR_INVALID_JSON = "invalid_json"
WS_ERROR_INVALID_FORMAT = "invalid_format"
WS_ERROR_UNKNOWN_COMMAND = "uknown_command"
WS_ERROR_UNKNOWN_ERROR = "uknown_error"
WS_ERROR_OLD_COMMAND_ID = "old_command_id"
WS_ERROR_SAVE_CONFIG_FAILED = "save_config_failed"


# Viseron data constants
WEBSOCKET_COMMANDS = "websocket_commands"
