"""License plate recognition constants."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "license_plate_recognition"


# Event topic constants
EVENT_LICENSE_PLATE_RECOGNITION_RESULT = (
    "{camera_identifier}/license_plate_recognition/result"
)
EVENT_LICENSE_PLATE_RECOGNITION_EXPIRED = (
    "{camera_identifier}/license_plate_recognition/expired"
)
EVENT_PLATE_DETECTED = "{camera_identifier}/license_plate_recognition/detected/{plate}"
EVENT_PLATE_EXPIRED = "{camera_identifier}/license_plate_recognition/expired/{plate}"


# BASE_CONFIG_SCHEMA constants
CONFIG_KNOWN_PLATES: Final = "known_plates"
CONFIG_SAVE_PLATES: Final = "save_plates"
CONFIG_MIN_CONFIDENCE: Final = "min_confidence"
CONFIG_EXPIRE_AFTER: Final = "expire_after"

DEFAULT_KNOWN_PLATES: list[str] = []
DEFAULT_SAVE_PLATES: Final = True
DEFAULT_EXPIRE_AFTER: Final = 5
DEFAULT_MIN_CONFIDENCE: Final = 0.6

DESC_KNOWN_PLATES: Final = (
    "List of known license plates. Each plate will have its own sensor."
)
DESC_SAVE_PLATES: Final = (
    "If set to <code>true</code>, detected license plates will be stored "
    "in the database, as well as having a snapshot saved."
)
DESC_EXPIRE_AFTER: Final = "Time in seconds before a plate recognition expires."
DESC_MIN_CONFIDENCE: Final = "Minimum confidence for a license plate detection."
