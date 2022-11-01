"""Compreface constants."""

COMPONENT = "compreface"


# CONFIG_SCHEMA constants
CONFIG_FACE_RECOGNITION = "face_recognition"
CONFIG_HOST = "host"
CONFIG_PORT = "port"
CONFIG_API_KEY = "recognition_api_key"

DESC_COMPONENT = "Compreface configuration."
DESC_FACE_RECOGNITION = "Face recognition domain config."
DESC_HOST = "IP or hostname to your Compreface server."
DESC_PORT = "Port to your Compreface server."
DESC_API_KEY = "API key to your Compreface recognition service."

# FACE_RECOGNITION_SCHEMA constants
CONFIG_TRAIN = "train"
CONFIG_DET_PROB_THRESHOLD = "det_prob_threshold"
CONFIG_LIMIT = "limit"
CONFIG_PREDICTION_COUNT = "prediction_count"
CONFIG_FACE_PLUGINS = "face_plugins"
CONFIG_STATUS = "status"

DEFAULT_TRAIN = False
DEFAULT_DET_PROB_THRESHOLD = 0.8
DEFAULT_LIMIT = 0
DEFAULT_PREDICTION_COUNT = 1
DEFAULT_FACE_PLUGINS = None
DEFAULT_STATUS = False

DESC_TRAIN = (
    "Train Compreface to recognize faces on Viseron start. "
    "Disable this when you have a good model trained."
)
DESC_DET_PROB_THRESHOLD = (
    "Minimum required confidence that a recognized face is actually a face. "
)
DESC_LIMIT = (
    "Maximum number of faces on the image to be recognized. "
    "It recognizes the biggest faces first. "
    "Value of 0 represents no limit."
)
DESC_PREDICTION_COUNT = (
    "Maximum number of subject predictions per face. "
    "It returns the most similar subjects."
)
DESC_FACE_PLUGINS = (
    "Comma-separated slugs of face plugins. "
    "If empty, no additional information is returned. "
    "<a href=https://github.com/exadel-inc/CompreFace/tree/master/docs/"
    "Face-services-and-plugins.md#face-plugins>Learn more</a>"
)
DESC_STATUS = (
    "If true includes system information like execution_time and plugin_version fields."
)
