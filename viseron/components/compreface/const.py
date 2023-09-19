"""CompreFace constants."""

from typing import Final

COMPONENT = "compreface"


# CONFIG_SCHEMA constants
CONFIG_FACE_RECOGNITION = "face_recognition"
CONFIG_HOST = "host"
CONFIG_PORT = "port"
CONFIG_API_KEY = "recognition_api_key"

DESC_COMPONENT = "CompreFace configuration."
DESC_FACE_RECOGNITION = "Face recognition domain config."
DESC_HOST = "IP or hostname to your CompreFace server."
DESC_PORT = "Port to your CompreFace server."
DESC_API_KEY = "API key to your CompreFace recognition service."

# FACE_RECOGNITION_SCHEMA constants
CONFIG_TRAIN = "train"
CONFIG_DET_PROB_THRESHOLD = "det_prob_threshold"
CONFIG_SIMILARITTY_THRESHOLD = "similarity_threshold"
CONFIG_LIMIT = "limit"
CONFIG_PREDICTION_COUNT = "prediction_count"
CONFIG_FACE_PLUGINS = "face_plugins"
CONFIG_STATUS = "status"
CONFIG_DETECT_REMOTE_FACES = "detect_remote_faces"

DEFAULT_TRAIN = False
DEFAULT_DET_PROB_THRESHOLD = 0.8
DEFAULT_SIMILARITTY_THRESHOLD = 0.5
DEFAULT_LIMIT = 0
DEFAULT_PREDICTION_COUNT = 1
DEFAULT_FACE_PLUGINS: Final = None
DEFAULT_STATUS = False
DEFAULT_DETECT_REMOTE_FACES = False

DESC_TRAIN = (
    "Train CompreFace to recognize faces on Viseron start. "
    "Disable this when you have a good model trained."
)
DESC_DET_PROB_THRESHOLD = (
    "Minimum required confidence that a recognized face is actually a face. "
)
DESC_SIMILARITY_THRESHOLD = (
    "CompreFace does not return <code>unknown</code> for faces that it does not "
    "recognize. If you upload the faces of two different people, you still receive "
    "the result, but the similarity is low. Any similarity below this threshold will "
    "be considered as an <code>unknown</code> face."
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
DESC_DETECT_REMOTE_FACES = "If true faces trained using other methods will be detected."
