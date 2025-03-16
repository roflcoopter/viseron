"""Gotify component constants."""

COMPONENT = "gotify"
DESC_COMPONENT = "Gotify server to send notifications for events."

CONFIG_GOTIFY_URL = "gotify_url"
CONFIG_GOTIFY_TOKEN = "gotify_token"
CONFIG_GOTIFY_PRIORITY = "priority"
CONFIG_GOTIFY_PRIORITY_DEFAULT = 5

CONFIG_CAMERAS = "cameras"
CONFIG_DETECTION_LABEL = "detection_label"
CONFIG_DETECTION_LABEL_DEFAULT = "person"
CONFIG_SEND_THUMBNAIL = "send_thumbnail"

# Camera-specific configuration options
CONFIG_CAMERA_DETECTION_LABEL = "detection_label"
CONFIG_CAMERA_SEND_THUMBNAIL = "send_thumbnail"

DESC_GOTIFY_URL = "Gotify server URL (e.g., https://gotify.example.com)."
DESC_GOTIFY_TOKEN = "Gotify application token."
DESC_GOTIFY_PRIORITY = "Priority of the notification (1-10)."
DESC_DETECTION_LABEL = "Label(s) of the object(s) to send notifications for (comma-separated for multiple labels, e.g., 'person,cat')."
DESC_SEND_THUMBNAIL = "Send a thumbnail of the detected object."

DESC_CAMERAS = "Cameras to get notifications from."

DESC_CAMERA_DETECTION_LABEL = "Label(s) of the object(s) to send notifications for this camera (comma-separated for multiple labels)."
DESC_CAMERA_SEND_THUMBNAIL = "Send a thumbnail of the detected object for this camera."
