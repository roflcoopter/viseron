"""Object detector domain constants."""
import os
from typing import Any, Final

from viseron.const import CONFIG_DIR

DOMAIN: Final = "object_detector"

MODEL_CACHE: Final = os.path.join(CONFIG_DIR, "models")

# Data stream topic constants
EVENT_OBJECT_DETECTOR_SCAN = "object_detector/{camera_identifier}/scan"
EVENT_OBJECT_DETECTOR_RESULT = "object_detector/{camera_identifier}/result"


# Event topic constants
EVENT_OBJECTS_IN_FOV = "{camera_identifier}/objects"
EVENT_OBJECTS_IN_ZONE = "{camera_identifier}/zone/{zone_name}/objects"


# LABEL_SCHEMA
CONFIG_LABEL_LABEL = "label"
CONFIG_LABEL_CONFIDENCE = "confidence"
CONFIG_LABEL_HEIGHT_MIN = "height_min"
CONFIG_LABEL_HEIGHT_MAX = "height_max"
CONFIG_LABEL_WIDTH_MIN = "width_min"
CONFIG_LABEL_WIDTH_MAX = "width_max"
CONFIG_LABEL_TRIGGER_RECORDER = "trigger_recorder"
CONFIG_LABEL_TRIGGER_EVENT_RECORDING = "trigger_event_recording"
CONFIG_LABEL_STORE = "store"
CONFIG_LABEL_STORE_INTERVAL = "store_interval"
CONFIG_LABEL_REQUIRE_MOTION = "require_motion"

DEFAULT_LABEL_CONFIDENCE = 0.8
DEFAULT_LABEL_HEIGHT_MIN = 0
DEFAULT_LABEL_HEIGHT_MAX = 1
DEFAULT_LABEL_WIDTH_MIN = 0
DEFAULT_LABEL_WIDTH_MAX = 1
DEFAULT_LABEL_TRIGGER_RECORDER = True
DEFAULT_LABEL_TRIGGER_EVENT_RECORDING = True
DEFAULT_LABEL_STORE = True
DEFAULT_LABEL_STORE_INTERVAL = 60
DEFAULT_LABEL_REQUIRE_MOTION = False

DESC_LABEL_LABEL = "The label to track."
DESC_LABEL_CONFIDENCE = (
    "Lowest confidence allowed for detected objects. "
    "The lower the value, the more sensitive the detector will be, "
    "and the risk of false positives will increase."
)
DESC_LABEL_HEIGHT_MIN = (
    "Minimum height allowed for detected objects, relative to stream height."
)
DESC_LABEL_HEIGHT_MAX = (
    "Maximum height allowed for detected objects, relative to stream height."
)
DESC_LABEL_WIDTH_MIN = (
    "Minimum width allowed for detected objects, relative to stream width."
)
DESC_LABEL_WIDTH_MAX = (
    "Maximum width allowed for detected objects, relative to stream width."
)
DESC_LABEL_TRIGGER_EVENT_RECORDING = (
    "If set to <code>true</code>, objects matching this filter will trigger an event "
    "recording."
)
DESC_LABEL_TRIGGER_RECORDER = (
    "If set to <code>true</code>, objects matching this filter will start the recorder."
)
DEPRECATED_LABEL_TRIGGER_RECORDER = "Use <code>trigger_event_recording</code> instead."
WARNING_LABEL_TRIGGER_RECORDER = (
    "Config option 'trigger_recorder' is deprecated and will be removed in a future "
    "version. Use 'trigger_event_recording' instead"
)
DESC_LABEL_REQUIRE_MOTION = (
    "If set to <code>true</code>, the recorder will stop as soon as motion is no "
    "longer detected, even if the object still is. This is useful to avoid never "
    "ending recordings of stationary objects, such as a car on a driveway"
)
DESC_LABEL_STORE = (
    "If set to <code>true</code>, objects matching this filter will be stored "
    "in the database, as well as having a snapshot saved. "
    "Labels with <code>trigger_event_recording</code> set to <code>true</code> will "
    "always be stored when a recording starts, regardless of this setting."
)
DESC_LABEL_STORE_INTERVAL = (
    "The interval at which the label should be stored in the database, in seconds. "
    "If set to 0, the label will be stored every time it is detected."
)

# CAMERA_SCHEMA constants
CONFIG_CAMERAS = "cameras"

CONFIG_FPS = "fps"
CONFIG_SCAN_ON_MOTION_ONLY = "scan_on_motion_only"
CONFIG_LABELS = "labels"
CONFIG_MAX_FRAME_AGE = "max_frame_age"
CONFIG_LOG_ALL_OBJECTS = "log_all_objects"
CONFIG_MASK = "mask"
CONFIG_ZONES = "zones"
CONFIG_COORDINATES = "coordinates"

DEFAULT_FPS = 1
DEFAULT_SCAN_ON_MOTION_ONLY = True
DEFAULT_LABELS: list[dict[str, str]] = []
DEFAULT_MAX_FRAME_AGE = 2
DEFAULT_LOG_ALL_OBJECTS = False
DEFAULT_MASK: list[dict[str, int]] = []
DEFAULT_ZONES: list[dict[str, Any]] = []

DESC_CAMERAS = (
    "Camera-specific configuration. All subordinate "
    "keys corresponds to the <code>camera_identifier</code> of a configured camera."
)

DESC_FPS = (
    "The FPS at which the object detector runs.<br>"
    "Higher values will result in more scanning, which uses more resources."
)
DESC_SCAN_ON_MOTION_ONLY = (
    "When set to <code>true</code> and a <code>motion_detector</code> is configured, "
    "the object detector will only scan while motion is detected."
)
DESC_LABELS = "A list of labels (objects) to track."
DESC_MAX_FRAME_AGE = (
    "Drop frames that are older than the given number. Specified in seconds."
)
DESC_LOG_ALL_OBJECTS = (
    "When set to true and loglevel is <code>DEBUG</code>, "
    "<b>all</b> found objects will be logged, "
    "including the ones not tracked by <code>labels</code>."
)
DESC_MASK = (
    "A mask is used to exclude certain areas in the image from object detection. "
)
DESC_ZONES = (
    "Zones are used to define areas in the cameras field of view where you want to "
    "look for certain objects (labels)."
)
DESC_COORDINATES = "List of X and Y coordinates to form a polygon"

# ZONE_SCHEMA constants
CONFIG_ZONE_NAME = "name"

DESC_ZONE_NAME = "Name of the zone. Has to be unique per camera."
