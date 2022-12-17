"""dlib constants."""

COMPONENT = "dlib"

# CONFIG_SCHEMA constants
CONFIG_FACE_RECOGNITION = "face_recognition"


# FACE_RECOGNITION_SCHEMA constants
CONFIG_MODEL = "model"

DESC_COMPONENT = "dlib configuration."
DESC_FACE_RECOGNITION = "Face recognition domain config."
DESC_MODEL = (
    "Which face recognition model to run. "
    "See <a href=#models>models</a> for more information on this."
)

SUPPORTED_MODELS = [
    "hog",
    "cnn",
]
