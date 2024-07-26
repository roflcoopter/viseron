"""Telegram-PTZ component constants."""

COMPONENT = "ptz"
DESC_COMPONENT = "Telegram bot to control pan-tilt-zoom cameras."

DEFAULT_RETAIN_CONFIG = True

CONFIG_TELEGRAM_BOT_TOKEN = "telegram_bot_token"
CONFIG_CAMERA_IP = "camera_ip"
CONFIG_CAMERA_PORT = "camera_port"
CONFIG_CAMERA_USERNAME = "camera_username"
CONFIG_CAMERA_PASSWORD = "camera_password"
CONFIG_CAMERA_NAME = "camera_name"
CONFIG_CAMERA_FULL_SWING_MIN_X = "camera_min_x"
CONFIG_CAMERA_FULL_SWING_MAX_X = "camera_max_x"

CONFIG_CAMERAS = "cameras"

DESC_TELEGRAM_BOT_TOKEN = "Telegram bot token."
DESC_CAMERA_IP = "IP address of the camera."
DESC_CAMERA_PORT = "ONVIF port of the camera."
DESC_CAMERA_USERNAME = "ONVIF username for the camera."
DESC_CAMERA_PASSWORD = "ONVIF password for the camera."
DESC_CAMERA_NAME = "Friendly name of the camera."
DESC_CAMERA_FULL_SWING_MIN_X = "Minimum pan value of the camera."
DESC_CAMERA_FULL_SWING_MAX_X = "Maximum pan value of the camera."

DESC_CAMERAS = "List of ONVIF cameras to control."
