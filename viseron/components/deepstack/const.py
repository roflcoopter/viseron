"""DeepStack constants."""
from typing import Final

COMPONENT = "deepstack"


# CONFIG_SCHEMA constants
CONFIG_OBJECT_DETECTOR = "object_detector"
CONFIG_FACE_RECOGNITION = "face_recognition"
CONFIG_HOST = "host"
CONFIG_PORT = "port"
CONFIG_API_KEY = "api_key"
CONFIG_TIMEOUT = "timeout"

DEFAULT_API_KEY: Final = None
DEFAULT_TIMEOUT = 10

DESC_COMPONENT = "DeepStack configuration."
DESC_OBJECT_DETECTOR = "Object detector domain config."
DESC_FACE_RECOGNITION = "Face recognition domain config."
DESC_HOST = "IP or hostname to your DeepStack server."
DESC_PORT = "Port to your DeepStack server."
DESC_API_KEY = "API key to your DeepStack server, if you have one set."
DESC_TIMEOUT = "Timeout for requests to your DeepStack server."

# OBJECT_DETECTOR_SCHEMA constants
CONFIG_IMAGE_WIDTH = "image_width"
CONFIG_IMAGE_HEIGHT = "image_height"
CONFIG_CUSTOM_MODEL = "custom_model"

DEFAULT_IMAGE_WIDTH: Final = None
DEFAULT_IMAGE_HEIGHT: Final = None
DEFAULT_CUSTOM_MODEL: Final = None

DESC_IMAGE_WIDTH = (
    "Frames will be resized to this width before inference to save computing power."
)
DESC_IMAGE_HEIGHT = (
    "Frames will be resized to this height before inference to save computing power."
)
DESC_CUSTOM_MODEL = (
    "Name of a custom DeepStack model. "
    "More information "
    "<a href=https://docs.deepstack.cc/custom-models/index.html>here</a>."
)

# FACE_RECOGNITION_SCHEMA constants
CONFIG_TRAIN = "train"
CONFIG_MIN_CONFIDENCE = "min_confidence"

DEFAULT_TRAIN = True
DEFAULT_MIN_CONFIDENCE = 0.8

DESC_TRAIN = (
    "Train DeepStack to recognize faces on Viseron start. "
    "Disable this when you have a good model trained."
)
DESC_MIN_CONFIDENCE = "Minimum confidence for a face to be considered a match."
