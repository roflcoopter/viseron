"""Webhook constants."""

from typing import Final

COMPONENT: Final = "webhook"


DESC_COMPONENT: Final = "Webhook component configuration."

SUPPORTED_METHODS = ["get", "patch", "post", "put", "delete"]

DESC_HOOK = "Hook configuration."

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
DESC_PASSWORD: Final = "Password for basic authentication."  # noqa: S105
DESC_PAYLOAD: Final = "Payload to send with the webhook request."
DESC_TIMEOUT: Final = "The timeout for the webhook request in seconds."
DESC_CONTENT_TYPE: Final = "The content type of the webhook request."
DESC_VERIFY_SSL: Final = "Whether to verify SSL certificates for the webhook request."
DESC_CA_CERT: Final = (
    "Path to a custom CA certificate bundle (PEM file or directory) used to "
    "verify the webhook server's TLS certificate. When set, it takes precedence "
    "over verify_ssl. Useful for servers fronted by a self-hosted Certificate "
    "Authority."
)


MESSAGE_AUTHENTICATION = "username and password must be provided together"
