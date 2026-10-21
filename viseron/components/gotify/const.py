"""Gotify component constants."""

from typing import Final

COMPONENT: Final = "gotify"
DESC_COMPONENT = "Gotify server to send notifications for events."

DEFAULT_PRIORITY = 5
DEFAULT_DETECTION_LABEL = "person"
DEFAULT_IMAGE_MAX_SIZE = 800
DEFAULT_IMAGE_QUALITY = 95

DESC_GOTIFY_URL = "Gotify server URL (e.g., https://gotify.example.com)."
DESC_GOTIFY_TOKEN = "Gotify application token."
DESC_GOTIFY_PRIORITY = "Priority of the notification (1-10)."
DESC_DETECTION_LABEL = (
    "Label(s) of the object(s) to send notifications for "
    "(comma-separated for multiple labels, e.g., 'person,cat')."
)
DESC_SEND_THUMBNAIL = "Send a thumbnail of the detected object."
DESC_USE_PUBLIC_URL = (
    "Use public URL for images instead of base64 encoding. "
    "This creates a temporary public link that doesn't require authentication."
)
DESC_IMAGE_MAX_SIZE = (
    "Maximum width/height in pixels for thumbnail images (default: 800). "
    "For 4K cameras, use 1920 or higher. Set to 0 for no resizing."
)
DESC_IMAGE_QUALITY = (
    "JPEG quality for images (1-100, default: 95). "
    "Higher = better quality but larger files."
)

DESC_CAMERAS = "Cameras to get notifications from."

DESC_CAMERA_DETECTION_LABEL = (
    "Label(s) of the object(s) to send notifications for this camera "
    "(comma-separated for multiple labels)."
)
DESC_CAMERA_SEND_THUMBNAIL = "Send a thumbnail of the detected object for this camera."
DESC_CAMERA_USE_PUBLIC_URL = (
    "Use public URL for images instead of base64 encoding for this camera."
)
