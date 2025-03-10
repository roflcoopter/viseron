"""Telegram-PTZ component constants."""

COMPONENT = "telegram"
DESC_COMPONENT = "Telegram bot to control pan-tilt-zoom cameras."

CONFIG_PTZ_COMPONENT = "ptz"

CONFIG_TELEGRAM_BOT_TOKEN = "telegram_bot_token"
CONFIG_TELEGRAM_CHAT_IDS = "telegram_chat_ids"
CONFIG_TELEGRAM_USER_IDS = "telegram_user_ids"
CONFIG_TELEGRAM_LOG_IDS = "telegram_log_ids"

CONFIG_CAMERAS = "cameras"
CONFIG_DETECTION_LABEL = "detection_label"
CONFIG_DETECTION_LABEL_DEFAULT = "person"

CONFIG_SEND_THUMBNAIL = "send_detection_thumbnail"
CONFIG_SEND_VIDEO = "send_detection_video"
CONFIG_SEND_MESSAGE = "send_detection_message"

DESC_TELEGRAM_BOT_TOKEN = "Telegram bot token."
DESC_TELEGRAM_CHAT_IDS = "List of chat IDs to send messages to."
DESC_TELEGRAM_USER_IDS = "List of user IDs to accept commands from."
DESC_TELEGRAM_LOG_IDS = "True if we should log the id of a user who was denied access."

DESC_DETECTION_LABEL = "Label of the object to send notifications for."
DESC_SEND_THUMBNAIL = "Send a thumbnail of the detected object."
DESC_SEND_VIDEO = "Send a video of the detected object."
DESC_SEND_MESSAGE = "Send a text message with the detected object."

DESC_CAMERAS = "Cameras to control with the Telegram bot and get notifications from."
