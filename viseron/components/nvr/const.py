"""NVR constants."""

from typing import Final

COMPONENT: Final = "nvr"
DOMAIN: Final = "nvr"

CAMERA: Final = "camera"
OBJECT_DETECTOR: Final = "object_detector"
MOTION_DETECTOR: Final = "motion_detector"
NO_DETECTOR: Final = "no_detector"
NO_DETECTOR_FPS: Final = 1

SCANNER_RESULT_RETRIES: Final = 5

# Data stream topic constants
DATA_PROCESSED_FRAME_TOPIC = "{camera_identifier}/nvr/processed_frame"


# Event topic constants
EVENT_OPERATION_STATE = "{camera_identifier}/nvr/operation_state"
EVENT_SCAN_FRAMES = "{camera_identifier}/nvr/{scanner_name}/scan"

DATA_NO_DETECTOR_SCAN = "no_detector/{camera_identifier}/scan"
DATA_NO_DETECTOR_RESULT = "no_detector/{camera_identifier}/result"

DESC_COMPONENT = "NVR configuration."
