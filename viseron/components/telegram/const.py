"""Telegram component constants."""

from typing import Final

COMPONENT: Final = "telegram"
DESC_COMPONENT = "Telegram bot to control cameras."

DATA_NOTIFIER: Final = "notifier"
DATA_PTZ: Final = "ptz"

DEFAULT_TELEGRAM_USER_IDS: list[int] = []
DEFAULT_SEND_THUMBNAIL: Final = False
DEFAULT_SEND_VIDEO: Final = False
DEFAULT_SEND_MESSAGE: Final = True
DEFAULT_TELEGRAM_LOG_IDS: Final = False
DEFAULT_DETECTION_LABELS: Final = ["person"]

DESC_TELEGRAM_BOT_TOKEN = "Telegram bot token."
DESC_TELEGRAM_CHAT_IDS = "List of chat IDs to send messages to."
DESC_TELEGRAM_USER_IDS = (
    "List of user IDs to accept commands from. Only applicable in public chats."
)
DESC_TELEGRAM_LOG_IDS = "True if we should log the id of a user who was denied access."

DESC_DETECTION_LABEL = "Deprecated. Use detection_labels instead."
DESC_DETECTION_LABELS = "Labels of objects to send notifications for."
DESC_SEND_THUMBNAIL = "Send a thumbnail of the detected object."
DESC_SEND_VIDEO = "Send a video of the detected object."
DESC_SEND_MESSAGE = "Send a text message with the detected object."

DESC_CAMERAS = "Cameras to control with the Telegram bot and get notifications from."
