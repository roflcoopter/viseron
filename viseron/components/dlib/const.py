"""dlib constants."""

from typing import Final

COMPONENT: Final = "dlib"

# CONFIG_SCHEMA constants
CONFIG_FACE_RECOGNITION: Final = "face_recognition"


# FACE_RECOGNITION_SCHEMA constants
CONFIG_MODEL: Final = "model"

DESC_COMPONENT: Final = "dlib configuration."
DESC_FACE_RECOGNITION: Final = "Face recognition domain config."
DESC_MODEL: Final = (
    "Which face recognition model to run. "
    "See <a href=#models>models</a> for more information on this."
)

SUPPORTED_MODELS: Final = [
    "hog",
    "cnn",
]

# Viseron data keys
CLASSIFIER: Final = "classifier"
