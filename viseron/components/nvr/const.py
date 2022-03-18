"""NVR constants."""

from typing import Final

COMPONENT: Final = "nvr"
DOMAIN: Final = "nvr"

CAMERA: Final = "camera"
OBJECT_DETECTOR: Final = "object_detector"
MOTION_DETECTOR: Final = "motion_detector"


# Data stream topic constants
DATA_PROCESSED_FRAME_TOPIC = "{camera_identifier}/nvr/processed_frame"


# Event topic constants
EVENT_OPERATION_STATE = "{camera_identifier}/nvr/operation_state"
