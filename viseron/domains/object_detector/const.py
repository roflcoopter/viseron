"""Object detector domain constants."""
from typing import Any, Dict, List

DATA_OBJECT_DETECTOR_SCAN = "object_detector/{camera_identifier}/scan"
DATA_OBJECT_DETECTOR_RESULT = "object_detector/{camera_identifier}/result"

EVENT_OBJECTS_IN_FOV = "{camera_identifier}/objects"


# LABEL_SCHEMA
CONFIG_LABEL_LABEL = "label"
CONFIG_LABEL_CONFIDENCE = "confidence"
CONFIG_LABEL_HEIGHT_MIN = "height_min"
CONFIG_LABEL_HEIGHT_MAX = "height_max"
CONFIG_LABEL_WIDTH_MIN = "width_min"
CONFIG_LABEL_WIDTH_MAX = "width_max"
CONFIG_LABEL_TRIGGER_RECORDER = "trigger_recorder"
CONFIG_LABEL_REQUIRE_MOTION = "require_motion"
CONFIG_LABEL_POST_PROCESSOR = "post_processor"

DEFAULT_LABEL_CONFIDENCE = 0.8
DEFAULT_LABEL_HEIGHT_MIN = 0
DEFAULT_LABEL_HEIGHT_MAX = 1
DEFAULT_LABEL_WIDTH_MIN = 0
DEFAULT_LABEL_WIDTH_MAX = 1
DEFAULT_LABEL_TRIGGER_RECORDER = True
DEFAULT_LABEL_REQUIRE_MOTION = False
DEFAULT_LABEL_POST_PROCESSOR = None


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
DEFAULT_LABELS: List[Dict[str, str]] = []
DEFAULT_MAX_FRAME_AGE = 2
DEFAULT_LOG_ALL_OBJECTS = False
DEFAULT_MASK: List[Dict[str, int]] = []
DEFAULT_ZONES: List[Dict[str, Any]] = []

# ZONE_SCHEMA constants
CONFIG_ZONE_NAME = "name"
