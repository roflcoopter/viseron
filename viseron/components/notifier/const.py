"""Telegram notifier component constants."""

COMPONENT = "notifier"
DESC_COMPONENT = "Telegram notifications of object detections."

CONFIG_TELEGRAM_BOT_TOKEN = "telegram_bot_token"
CONFIG_TELEGRAM_CHAT_IDS = "telegram_chat_ids"

CONFIG_CAMERAS = "cameras"
CONFIG_DETECTION_LABEL = "detection_label"

CONFIG_SEND_THUMBNAIL = "send_thumbnail"
CONFIG_SEND_VIDEO = "send_video"

DESC_TELEGRAM_BOT_TOKEN = "Telegram bot token."
DESC_TELEGRAM_CHAT_IDS = "List of allowed Telegram chat IDs."
DESC_DETECTION_LABEL = "Label of the object to send notifications for."

DESC_SEND_THUMBNAIL = "Send a thumbnail of the detected object."
DESC_SEND_VIDEO = "Send a video of the detected object."

DESC_CAMERAS = (
    "Camera-specific configuration. All subordinate "
    "keys corresponds to the <code>camera_identifier</code> of a configured camera."
)
