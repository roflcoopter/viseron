"""Motion detector domain constants."""
from typing import Dict, Final, List

DOMAIN: Final = "motion_detector"


# Data stream topic constants
DATA_MOTION_DETECTOR_SCAN = "motion_detector/{camera_identifier}/scan"
DATA_MOTION_DETECTOR_RESULT = "motion_detector/{camera_identifier}/result"


# Event topic constants
EVENT_MOTION_DETECTED = "{camera_identifier}/motion_detected"


# CAMERA_SCHEMA constants
CONFIG_CAMERAS = "cameras"

CONFIG_FPS = "fps"
CONFIG_AREA = "area"
CONFIG_WIDTH = "width"
CONFIG_HEIGHT = "height"
CONFIG_MASK = "mask"
CONFIG_COORDINATES = "coordinates"
CONFIG_TRIGGER_RECORDER = "trigger_recorder"
CONFIG_RECORDER_KEEPALIVE = "recorder_keepalive"
CONFIG_MAX_RECORDER_KEEPALIVE = "max_recorder_keepalive"

DEFAULT_FPS = 1
DEFAULT_AREA = 0.08
DEFAULT_WIDTH = 300
DEFAULT_HEIGHT = 300
DEFAULT_MASK: List[Dict[str, int]] = []
DEFAULT_TRIGGER_RECORDER = False
DEFAULT_RECORDER_KEEPALIVE = True
DEFAULT_MAX_RECORDER_KEEPALIVE = 30
