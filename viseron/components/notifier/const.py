"""Notifier component constants."""

from typing import Final

COMPONENT = "notifier"
DESC_COMPONENT = "Notifier configuration."

DEFAULT_RETAIN_CONFIG = True

# CONFIG_SCHEMA constants
CONFIG_SMTP_SERVER = "smtp_server"
CONFIG_SMTP_PORT = "smtp_port"
CONFIG_SMTP_USERNAME = "smtp_username"
CONFIG_SMTP_PASSWORD = "smtp_password"
CONFIG_SMTP_RECIPIENTS = "smtp_recipients"
CONFIG_SMTP_SENDER = "smtp_sender"

CONFIG_TELEGRAM_BOT_TOKEN = "telegram_bot_token"
CONFIG_TELEGRAM_CHAT_ID = "telegram_chat_id"

CONFIG_CAMERAS = "cameras"

DEFAULT_PORT = 587
DEFAULT_USERNAME: Final = None
DEFAULT_PASSWORD: Final = None

DESC_SMTP_SERVER = "IP address or hostname of SMTP server."
DESC_SMTP_PORT = "Port the SMTP server is listening on."
DESC_SMTP_USERNAME = "Username for the SMTP server."
DESC_SMTP_PASSWORD = "Password for the SMTP server."
DESC_SMTP_RECIPIENTS = "Recipients of the email."
DESC_SMTP_SENDER = "Sender of the email."

DESC_TELEGRAM_BOT_TOKEN = "Telegram bot token."
DESC_TELEGRAM_CHAT_ID = "Telegram chat ID."

DESC_CAMERAS = (
    "Camera-specific configuration. All subordinate "
    "keys corresponds to the <code>camera_identifier</code> of a configured camera."
)
