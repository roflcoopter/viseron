"""Background subtractor detection constants."""

COMPONENT = "background_subtractor"


# MOTION_DETECTOR_SCHEMA constants
CONFIG_THRESHOLD = "threshold"
CONFIG_ALPHA = "alpha"

DEFAULT_THRESHOLD = 15
DEFAULT_ALPHA = 0.1

DESC_COMPONENT = "Component configuration."
DESC_THRESHOLD = (
    "The minimum allowed difference between our current frame and averaged frame for a "
    "given pixel to be considered motion. A smaller value leads to higher sensitivity "
    "and a larger value leads to lower sensitivity."
)
DESC_ALPHA = (
    "How much the current image impacts the moving average.<br>"
    "Higher values impacts the average frame a lot and very small changes may "
    "trigger motion.<br>Lower value impacts the average less, "
    "and fast objects may not trigger motion. "
    "More can be read <a href=https://docs.opencv.org/3.4/d7/df3/group__imgproc__motion"
    ".html#ga4f9552b541187f61f6818e8d2d826bc7>here</a>."
)

# CONFIG_SCHEMA constants
CONFIG_MOTION_DETECTOR = "motion_detector"

DESC_MOTION_DETECTOR = "Motion detector domain config."
