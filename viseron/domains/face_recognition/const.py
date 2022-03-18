"""Face recognition constants."""
from typing import Final

DOMAIN: Final = "face_recognition"


# Event topic constants
EVENT_FACE_DETECTED = "{camera_identifier}/face/detected/{face}"
EVENT_FACE_EXPIRED = "{camera_identifier}/face/expired/{face}"


# BASE_CONFIG_SCHEMA constants
CONFIG_CAMERAS = "cameras"
CONFIG_FACE_RECOGNITION_PATH = "face_recognition_path"
CONFIG_SAVE_UNKNOWN_FACES = "save_unknown_faces"
CONFIG_UNKNOWN_FACES_PATH = "unknown_faces_path"
CONFIG_EXPIRE_AFTER = "expire_after"

DEFAULT_FACE_RECOGNITION_PATH = "/config/face_recognition/faces"
DEFAULT_SAVE_UNKNOWN_FACES = False
DEFAULT_UNKNOWN_FACES_PATH = f"{DEFAULT_FACE_RECOGNITION_PATH}/unknown"
DEFAULT_EXPIRE_AFTER = 5
