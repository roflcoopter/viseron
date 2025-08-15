"""Webhook constants."""
from typing import Final

COMPONENT = "webhook"


# CONFIG_SCHEMA constants
DESC_COMPONENT: Final = "Webhook component configuration."

SUPPORTED_METHODS = ["get", "patch", "post", "put", "delete"]

DESC_HOOK = "Hook configuration."
CONFIG_TRIGGER: Final = "trigger"
CONFIG_EVENT: Final = "event"
CONFIG_CONDITION: Final = "condition"
CONFIG_URL: Final = "url"
CONFIG_METHOD: Final = "method"
CONFIG_HEADERS: Final = "headers"
CONFIG_USERNAME: Final = "username"
CONFIG_PASSWORD: Final = "password"
CONFIG_PAYLOAD: Final = "payload"
CONFIG_TIMEOUT: Final = "timeout"
CONFIG_CONTENT_TYPE: Final = "content_type"
CONFIG_VERIFY_SSL: Final = "verify_ssl"

DEFAULT_CONDITION: Final = None
DEFAULT_HEADERS: Final = None
DEFAULT_USERNAME: Final = None
DEFAULT_PASSWORD: Final = None
DEFAULT_PAYLOAD: Final = None
DEFAULT_CONTENT_TYPE: Final = "application/json"
DEFAULT_TIMEOUT: Final = 10
DEFAULT_METHOD: Final = "get"
DEFAULT_VERIFY_SSL: Final = True

DESC_TRIGGER: Final = "The trigger configuration for the webhook."
DESC_EVENT: Final = "The event type that triggers the webhook."
DESC_CONDITION: Final = (
    "Template condition to check before sending the webhook. "
    "If set, the webhook will only be sent if the template evaluates to a "
    "truthy value (True, true, 1, yes, on)."
)
DESC_URL: Final = "The URL to send the webhook request to."
DESC_METHOD: Final = "The HTTP method to use for the webhook request."
DESC_HEADERS: Final = "Headers to include in the webhook request."
DESC_HEADER: Final = "Header key for the webhook request."
DESC_USERNAME: Final = "Username for basic authentication."
DESC_PASSWORD: Final = "Password for basic authentication."
DESC_PAYLOAD: Final = "Payload to send with the webhook request."
DESC_TIMEOUT: Final = "The timeout for the webhook request in seconds."
DESC_CONTENT_TYPE: Final = "The content type of the webhook request."
DESC_VERIFY_SSL: Final = "Whether to verify SSL certificates for the webhook request."

INCLUSION_GROUP_AUTHENTICATION: Final = "authentication"

MESSAGE_AUTHENTICATION = "username and password must be provided together"
