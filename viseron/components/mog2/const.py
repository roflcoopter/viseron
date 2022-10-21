"""Background Subtractor MOG2 motion detection constants."""

COMPONENT = "mog2"

# MOTION_DETECTOR_SCHEMA constants
CONFIG_THRESHOLD = "threshold"
CONFIG_HISTORY = "history"
CONFIG_DETECT_SHADOWS = "detect_shadows"
CONFIG_LEARNING_RATE = "learning_rate"

DEFAULT_THRESHOLD = 15
DEFAULT_HISTORY = 500
DEFAULT_DETECT_SHADOWS = False
DEFAULT_LEARNING_RATE = 0.01

DESC_COMPONENT = "MOG2 configuration."
DESC_THRESHOLD = (
    "The minimum allowed difference between our current frame and averaged frame for a "
    "given pixel to be considered motion. A smaller value leads to higher sensitivity "
    "and a larger value leads to lower sensitivity."
)
DESC_HISTORY = "The number of last frames that affect the background model."
DESC_DETECT_SHADOWS = (
    "Enable/disable shadow detection. If enabled, shadows will be considered as motion "
    "at the expense of some extra resources."
)
DESC_LEARNING_RATE = (
    "How fast the background model learns. 0 means that the background model is not "
    "updated at all, 1 means that the background model is completely reinitialized "
    "from the last frame. "
    "Negative values gives an automatically chosen learning rate."
)


# CONFIG_SCHEMA constants
CONFIG_MOTION_DETECTOR = "motion_detector"

DESC_MOTION_DETECTOR = "Motion detector domain config."
