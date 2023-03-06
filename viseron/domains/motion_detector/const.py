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

DESC_CAMERAS = (
    "Camera-specific configuration. All subordinate "
    "keys corresponds to the <code>camera_identifier</code> of a configured camera."
)
DESC_FPS = (
    "The FPS at which the motion detector runs.<br>"
    "Higher values will result in more scanning, which uses more resources."
)
DESC_AREA = "How big the detected area must be in order to trigger motion."
DESC_WIDTH = (
    "Frames will be resized to this width before applying the motion detection "
    "algorithm to save computing power."
)
DESC_HEIGHT = (
    "Frames will be resized to this height before applying the motion detection "
    "algorithm to save computing power."
)
DESC_MASK = (
    "A mask is used to exclude certain areas in the image from motion detection. "
)
DESC_COORDINATES = "List of X and Y coordinates to form a polygon"
DESC_TRIGGER_RECORDER = "If true, detected motion will start the recorder."
DESC_RECORDER_KEEPALIVE = (
    "If true, recording will continue until no motion is detected."
)
DESC_MAX_RECORDER_KEEPALIVE = (
    "Value in seconds for how long motion is allowed to keep the "
    "recorder going when no objects are detected.<br>"
    "Use this to prevent never-ending recordings.<br>"
    "Only applicable if <code>recorder_keepalive: true</code>.<br>"
    "<b>A value of <code>0</code> disables this functionality.</b>"
)
