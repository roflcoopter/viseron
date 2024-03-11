"""Camera domain constants."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "camera"

UPDATE_TOKEN_INTERVAL_MINUTES: Final = 5

VIDEO_CONTAINER = "mp4"

# Event topic constants
EVENT_STATUS = "{camera_identifier}/camera/status"
EVENT_STATUS_DISCONNECTED = "disconnected"
EVENT_STATUS_CONNECTED = "connected"

EVENT_RECORDER_START = "{camera_identifier}/recorder/start"
EVENT_RECORDER_STOP = "{camera_identifier}/recorder/stop"
EVENT_RECORDER_COMPLETE = "{camera_identifier}/recorder/complete"

EVENT_CAMERA_START = "{camera_identifier}/camera/start"
EVENT_CAMERA_STOP = "{camera_identifier}/camera/stop"
EVENT_CAMERA_STARTED = "{camera_identifier}/camera/started"
EVENT_CAMERA_STOPPED = "{camera_identifier}/camera/stopped"


# MJPEG_STREAM_SCHEMA constants
CONFIG_MJPEG_WIDTH = "width"
CONFIG_MJPEG_HEIGHT = "height"
CONFIG_MJPEG_DRAW_OBJECTS = "draw_objects"
CONFIG_MJPEG_DRAW_MOTION = "draw_motion"
CONFIG_MJPEG_DRAW_MOTION_MASK = "draw_motion_mask"
CONFIG_MJPEG_DRAW_OBJECT_MASK = "draw_object_mask"
CONFIG_MJPEG_DRAW_ZONES = "draw_zones"
CONFIG_MJPEG_ROTATE = "rotate"
CONFIG_MJPEG_MIRROR = "mirror"

DEFAULT_MJPEG_WIDTH = 0
DEFAULT_MJPEG_HEIGHT = 0
DEFAULT_MJPEG_DRAW_OBJECTS = False
DEFAULT_MJPEG_DRAW_MOTION = False
DEFAULT_MJPEG_DRAW_MOTION_MASK = False
DEFAULT_MJPEG_DRAW_OBJECT_MASK = False
DEFAULT_MJPEG_DRAW_ZONES = False
DEFAULT_MJPEG_ROTATE = 0
DEFAULT_MJPEG_MIRROR = False

DESC_MJPEG_WIDTH = "Frame will be rezied to this width. Required if height is set."
DESC_MJPEG_HEIGHT = "Frame will be rezied to this height. Required if width is set."
DESC_MJPEG_DRAW_OBJECTS = "If set, found objects will be drawn."
DESC_MJPEG_DRAW_MOTION = "If set, detected motion will be drawn."
DESC_MJPEG_DRAW_MOTION_MASK = "If set, configured motion masks will be drawn."
DESC_MJPEG_DRAW_OBJECT_MASK = "If set, configured object masks will be drawn."
DESC_MJPEG_DRAW_ZONES = "If set, configured zones will be drawn."
DESC_MJPEG_ROTATE = (
    "Degrees to rotate the image. "
    "Positive/negative values rotate clockwise/counter clockwise respectively"
)
DESC_MJPEG_MIRROR = "If set, mirror the image horizontally."


# THUMBNAIL_SCHEMA constants
CONFIG_SAVE_TO_DISK = "save_to_disk"

DEFAULT_SAVE_TO_DISK = True

DESC_SAVE_TO_DISK = (
    "If <code>true</code>, the thumbnail that is created on start of recording is "
    "saved to <code>{camera_identifier}/latest_thumbnail.jpg</code><br>"
    "Full path depends on the "
    "<a href=/components-explorer/components/storage>storage component</a> "
    "tier configuration."
)


# RECORDER_SCHEMA constants
CONFIG_LOOKBACK = "lookback"
CONFIG_IDLE_TIMEOUT = "idle_timeout"
CONFIG_RETAIN = "retain"
CONFIG_FOLDER = "folder"
CONFIG_FILENAME_PATTERN = "filename_pattern"
CONFIG_EXTENSION = "extension"
CONFIG_THUMBNAIL = "thumbnail"
CONFIG_CREATE_EVENT_CLIP: Final = "create_event_clip"
CONFIG_STORAGE = "storage"

DEFAULT_LOOKBACK = 5
DEFAULT_IDLE_TIMEOUT = 10
DEFAULT_FILENAME_PATTERN = "%H:%M:%S"
DEFAULT_THUMBNAIL: Final = None
DEFAULT_CREATE_EVENT_CLIP = False
DEFAULT_STORAGE: Final = None
DEFAULT_RECORDER_TIERS: Final = None

DESC_LOOKBACK = "Number of seconds to record before a detected object."
DESC_IDLE_TIMEOUT = "Number of seconds to record after all events are over."
DESC_RETAIN = "Number of days to save recordings before deletion."
DEPRECATED_RETAIN = (
    "Use the "
    "<a href=/components-explorer/components/storage>storage component</a> instead."
)
WARNING_RETAIN = (
    "Config option 'retain' is deprecated and will be removed in a future version. "
    "Please use 'max_age' in the 'storage' component instead."
)
DESC_FOLDER = "What folder to store recordings in."
DEPRECATED_FOLDER = (
    "Use the "
    "<a href=/components-explorer/components/storage>storage component</a> instead."
)
WARNING_FOLDER = (
    "Config option 'folder' is deprecated and will be removed in a future version. "
    "Please use the 'storage' component instead."
)
DESC_FILENAME_PATTERN = (
    "A <a href=https://strftime.org/>strftime</a> pattern for saved recordings.<br>"
    "Default pattern results in filenames like: <code>23:59:59.jpg</code>."
)
DESC_EXTENSION = "The file extension used for recordings."
DEPRECATED_EXTENSION = "<code>mp4</code> is the only supported extension."
WARNING_EXTENSION = (
    "Config option 'extension' is deprecated and will be removed in a "
    "future version. 'mp4' is the only supported extension."
)

DESC_THUMBNAIL = "Options for the thumbnail created on start of a recording."
DESC_FILENAME_PATTERN_THUMBNAIL = (
    "A <a href=https://strftime.org/>strftime</a> pattern for saved thumbnails.<br>"
    "Default pattern results in filenames like: <code>23:59:59.jpg</code>."
)
DEPRECATED_FILENAME_PATTERN_THUMBNAIL = (
    "Thumbnails are stored with the same filename as the recording ID in the "
    "database, for example: 1.jpg, 2.jpg, 3.jpg etc."
)
WARNING_FILENAME_PATTERN_THUMBNAIL = (
    "Config option 'filename_pattern' is deprecated and will be removed in a future "
    "version. {DEPRECATED_FILENAME_PATTERN_THUMBNAIL}"
)

DESC_STORAGE = (
    "Storage options for the camera.<br>"
    "Overrides the configuration in the "
    "<a href=/components-explorer/components/storage>storage component</a>."
)
DESC_CREATE_EVENT_CLIP = (
    "Concatenate fragments to an MP4 file for each event. "
    "WARNING: Will store both the fragments AND the MP4 file, using more storage space."
)

# STILL_IMAGE_SCHEMA constants
CONFIG_STILL_IMAGE = "still_image"
CONFIG_URL = "url"
CONFIG_USERNAME = "username"
CONFIG_PASSWORD = "password"
CONFIG_AUTHENTICATION = "authentication"
CONFIG_REFRESH_INTERVAL = "refresh_interval"

DEFAULT_STILL_IMAGE: Final = None
DEFAULT_URL: Final = None
DEFAULT_USERNAME: Final = None
DEFAULT_PASSWORD: Final = None
DEFAULT_AUTHENTICATION: Final = None
DEFAULT_REFRESH_INTERVAL: Final = 10

DESC_STILL_IMAGE = "Options for still image."
DESC_URL = (
    "URL to the still image. "
    "If this is omitted, the camera stream will be used to get the image."
)
DESC_USERNAME = (
    "Username for authentication.<br>Only applicable if <code>url</code> is set."
)
DESC_PASSWORD = (
    "Password for authentication.<br>Only applicable if <code>url</code> is set."
)
DESC_AUTHENTICATION = (
    "Authentication method to use.<br>Only applicable if <code>url</code> is set."
)
DESC_REFRESH_INTERVAL = (
    "Number of seconds between refreshes of the still image in the frontend."
)

INCLUSION_GROUP_AUTHENTICATION = "authentication"

AUTHENTICATION_BASIC = "basic"
AUTHENTICATION_DIGEST = "digest"

# BASE_CONFIG_SCHEMA constants
CONFIG_NAME = "name"
CONFIG_MJPEG_STREAMS = "mjpeg_streams"
CONFIG_RECORDER = "recorder"

DEFAULT_NAME: Final = None
DEFAULT_MJPEG_STREAMS: Final = None
DEFAULT_RECORDER: Final = None

DESC_NAME = "Camera friendly name."
DESC_MJPEG_STREAMS = "MJPEG streams config."
DESC_RECORDER = "Recorder config."
DESC_MJPEG_STREAM = (
    "Name of the MJPEG stream. Used to build the URL to access the stream.<br>"
    "Valid characters are lowercase a-z, numbers and underscores."
)
