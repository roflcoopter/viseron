"""CodeProject.AI constants."""
from typing import Final

COMPONENT = "codeprojectai"

PLATE_RECOGNITION_URL_BASE = "http://{host}:{port}/v1/image/alpr"


# CONFIG_SCHEMA constants
CONFIG_OBJECT_DETECTOR = "object_detector"
CONFIG_FACE_RECOGNITION = "face_recognition"
CONFIG_LICENSE_PLATE_RECOGNITION = "license_plate_recognition"
CONFIG_HOST = "host"
CONFIG_PORT = "port"
CONFIG_TIMEOUT = "timeout"

DEFAULT_PORT = 32168
DEFAULT_TIMEOUT = 10

DESC_COMPONENT = "CodeProject.AI configuration."
DESC_OBJECT_DETECTOR = "Object detector domain config."
DESC_FACE_RECOGNITION = "Face recognition domain config."
DESC_LICENSE_PLATE_RECOGNITION = "License plate recognition domain config."
DESC_HOST = "IP or hostname to your CodeProject.AI server."
DESC_PORT = "Port to your CodeProject.AI server."
DESC_TIMEOUT = "Timeout for requests to your CodeProject.AI server."

# OBJECT_DETECTOR_SCHEMA constants
CONFIG_IMAGE_SIZE = "image_size"
CONFIG_CUSTOM_MODEL = "custom_model"

DEFAULT_IMAGE_SIZE: Final = None
DEFAULT_CUSTOM_MODEL: Final = "ipcam-general"

DESC_IMAGE_SIZE = (
    "Frames will be resized to this width and height before inference to save "
    "computing power. Resizing is done by adding black borders to the image to keep "
    "the aspect ratio."
)
DESC_CUSTOM_MODEL = "Name of a custom CodeProject.AI model."

# FACE_RECOGNITION_SCHEMA constants
CONFIG_TRAIN = "train"
CONFIG_MIN_CONFIDENCE = "min_confidence"

DEFAULT_TRAIN = True
DEFAULT_MIN_CONFIDENCE = 0.6

DESC_TRAIN = (
    "Train CodeProject.AI to recognize faces on Viseron start. "
    "Disable this when you have a good model trained."
)
DESC_MIN_CONFIDENCE = "Minimum confidence for a face to be considered a match."
