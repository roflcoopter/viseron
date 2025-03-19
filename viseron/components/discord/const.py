"""Discord component constants."""

COMPONENT = "discord"
DESC_COMPONENT = "Discord webhook to send notifications."

CONFIG_DISCORD_WEBHOOK_URL = "webhook_url"
CONFIG_CAMERAS = "cameras"
CONFIG_DETECTION_LABEL = "detection_label"
CONFIG_DETECTION_LABEL_DEFAULT = "person"
CONFIG_SEND_THUMBNAIL = "send_detection_thumbnail"
CONFIG_SEND_VIDEO = "send_detection_video"
CONFIG_MAX_VIDEO_SIZE_MB = "max_video_size_mb"
CONFIG_MAX_VIDEO_SIZE_MB_DEFAULT = 8

DESC_DISCORD_WEBHOOK_URL = "Discord webhook URL. Can be overridden per camera."
DESC_DETECTION_LABEL = "Label of the object to send notifications for."
DESC_SEND_THUMBNAIL = "Send a thumbnail of the detected object."
DESC_SEND_VIDEO = "Send a video of the detected object."
DESC_MAX_VIDEO_SIZE_MB = (
    "Maximum size of video to send in MB "
    "(Discord limit is 8MB for free tier, 50MB for level 2 boosted servers "
    "and 100MB for level 3 boosted servers)."
)
DESC_CAMERAS = "Cameras to get notifications from."
