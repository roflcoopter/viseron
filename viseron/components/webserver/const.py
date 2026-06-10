"""Webserver constants."""

from datetime import timedelta
from typing import Final

from viseron.const import CONFIG_DIR

COMPONENT: Final = "webserver"

WEBSERVER_STORAGE_KEY = "webserver"
AUTH_STORAGE_KEY = "auth"
ONBOARDING_STORAGE_KEY = "onboarding"

ACCESS_TOKEN_EXPIRATION = timedelta(minutes=30)
MAX_FILE_SEARCH_TRIES = 10

DOWNLOAD_PATH = "/tmp/downloads"
PUBLIC_IMAGES_PATH = f"{CONFIG_DIR}/public_images"

# CONFIG_SCHEMA constants
CONFIG_PORT = "port"
CONFIG_DEBUG = "debug"
CONFIG_PUBLIC_BASE_URL = "public_base_url"
CONFIG_PUBLIC_URL_EXPIRY_HOURS = "public_url_expiry_hours"
CONFIG_PUBLIC_URL_MAX_DOWNLOADS = "public_url_max_downloads"

DEFAULT_COMPONENT: Final = None
DEFAULT_DEBUG = False
DEFAULT_PUBLIC_URL_EXPIRY_HOURS = 24
DEFAULT_PUBLIC_URL_MAX_DOWNLOADS = 0

CONFIG_SUBPATH = "subpath"
DEFAULT_SUBPATH: Final = None

DESC_COMPONENT = "Webserver configuration."

DESC_PORT = "Port to run the webserver on."
DESC_DEBUG = (
    "Enable debug mode for the webserver. <b>WARNING: Dont have this enabled in"
    " production as it weakens security.</b>"
)
DESC_PUBLIC_BASE_URL = (
    "Public base URL for Viseron (e.g., https://viseron.example.com). "
    "Used for generating public links accessible from outside your network."
)
DESC_PUBLIC_URL_EXPIRY_HOURS = (
    "Number of hours before public image URLs expire (default: 24, max: 744 = 31 days)."
)
DESC_PUBLIC_URL_MAX_DOWNLOADS = (
    "Maximum number of times a public image URL can be downloaded before it is"
    " automatically deleted. Set to 0 for unlimited downloads (default: 0 = unlimited)."
)
DESC_SUBPATH = (
    "Subpath where the webserver is served from when behind a reverse proxy "
    "(e.g. '/viseron')."
)

# Auth constants
CONFIG_AUTH = "auth"
CONFIG_LDAP = "ldap"
CONFIG_ENABLED = "enabled"
CONFIG_URL = "url"
CONFIG_BIND_DN = "bind_dn"
CONFIG_BIND_PASSWORD = "bind_password"
CONFIG_USER_BASE_DN = "user_base_dn"
CONFIG_USER_FILTER = "user_filter"
CONFIG_USERNAME_ATTRIBUTE = "username_attribute"
CONFIG_NAME_ATTRIBUTE = "name_attribute"
CONFIG_GROUP_BASE_DN = "group_base_dn"
CONFIG_GROUP_FILTER = "group_filter"
CONFIG_ADMIN_GROUPS = "admin_groups"
CONFIG_WRITE_GROUPS = "write_groups"
CONFIG_READ_GROUPS = "read_groups"
CONFIG_DEFAULT_ROLE = "default_role"
CONFIG_CAMERA_GROUPS = "camera_groups"
CONFIG_LDAP_CAMERA_ACCESS = "ldap_camera_access"
CONFIG_GROUPS = "groups"
CONFIG_CAMERAS = "cameras"
CONFIG_SESSION_EXPIRY = "session_expiry"
CONFIG_DAYS = "days"
CONFIG_HOURS = "hours"
CONFIG_MINUTES = "minutes"
CONFIG_RATE_LIMITS = "rate_limits"
CONFIG_RATE_LIMIT_LOGIN = "login"
CONFIG_RATE_LIMIT_TOKEN = "token"  # noqa: S105
CONFIG_RATE_LIMIT_ONBOARDING = "onboarding"
CONFIG_MAX_ATTEMPTS = "max_attempts"
CONFIG_WINDOW_SECONDS = "window_seconds"

DEFAULT_SESSION_EXPIRY: Final = None
DEFAULT_RATE_LIMIT_LOGIN: Final = {"max_attempts": 10, "window_seconds": 60}
DEFAULT_RATE_LIMIT_TOKEN: Final = {"max_attempts": 30, "window_seconds": 60}
DEFAULT_RATE_LIMIT_ONBOARDING: Final = {"max_attempts": 5, "window_seconds": 60}
DEFAULT_LDAP_USER_FILTER: Final = "(sAMAccountName={username})"
DEFAULT_LDAP_GROUP_FILTER: Final = "(member={user_dn})"
DEFAULT_LDAP_USERNAME_ATTRIBUTE: Final = "sAMAccountName"
DEFAULT_LDAP_NAME_ATTRIBUTE: Final = "displayName"
DEFAULT_LDAP_DEFAULT_ROLE: Final = "deny"

DESC_AUTH = "Authentication configuration."
DESC_LDAP = "LDAP/Active Directory authentication configuration."
DESC_ENABLED = "Enable this integration."
DESC_URL = (
    "LDAP server URL, for example ldap://dc.example.org or ldaps://dc.example.org."
)
DESC_BIND_DN = "LDAP bind DN used to search users. Leave empty for anonymous bind."
DESC_BIND_PASSWORD = "Password for bind_dn."
DESC_USER_BASE_DN = "Base DN used to search users."
DESC_USER_FILTER = (
    "LDAP user search filter. Supports {username}. The default targets Active "
    "Directory sAMAccountName."
)
DESC_USERNAME_ATTRIBUTE = "LDAP attribute used as username."
DESC_NAME_ATTRIBUTE = "LDAP attribute used as display name."
DESC_GROUP_BASE_DN = "Base DN used to search groups. Leave empty to use memberOf."
DESC_GROUP_FILTER = "LDAP group search filter. Supports {user_dn} and {username}."
DESC_ADMIN_GROUPS = "LDAP groups mapped to the Viseron admin role."
DESC_WRITE_GROUPS = "LDAP groups mapped to the Viseron write role."
DESC_READ_GROUPS = "LDAP groups mapped to the Viseron read role."
DESC_DEFAULT_ROLE = "Role assigned when no LDAP group mapping matches."
DESC_CAMERA_GROUPS = "Named groups of cameras used for access control."
DESC_LDAP_CAMERA_ACCESS = "LDAP groups mapped to camera groups or cameras."
DESC_SESSION_EXPIRY = (
    "Session expiry time. After this time the user will be logged out. By default the"
    " sessions are infinite."
)
DESC_DAYS = "Days to expire session."
DESC_HOURS = "Hours to expire session."
DESC_MINUTES = "Minutes to expire session."
DESC_RATE_LIMITS = (
    "Per-IP rate limits applied to authentication endpoints. Tune these if you have"
    " many legitimate clients behind a single IP, or lower them to harden against"
    " brute force."
)
DESC_RATE_LIMIT_LOGIN = "Rate limit for the login endpoint (POST /api/v1/auth/login)."
DESC_RATE_LIMIT_TOKEN = (
    "Rate limit for the token endpoint (POST /api/v1/auth/token), "  # noqa: S105
    "used to refresh access tokens."
)
DESC_RATE_LIMIT_ONBOARDING = (
    "Rate limit for the initial onboarding endpoint (POST /api/v1/onboarding)."
)
DESC_MAX_ATTEMPTS = "Maximum number of attempts allowed within the window."
DESC_WINDOW_SECONDS = "Length of the sliding window in seconds."

# Websocket constants
TYPE_RESULT = "result"
TYPE_SUBSCRIPTION_RESULT = "subscription_result"
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
WS_ERROR_RELOAD_CONFIG_FAILED = "reload_config_failed"
WS_ERROR_NOT_FOUND = "not_found"
WS_ERROR_UNAUTHORIZED = "unauthorized"


# Viseron data constants
WEBSOCKET_COMMANDS: Final = "websocket_commands"
WEBSOCKET_CONNECTIONS: Final = "websocket_connections"
DOWNLOAD_TOKENS: Final = "download_tokens"
PUBLIC_IMAGE_TOKENS: Final = "public_image_tokens"
