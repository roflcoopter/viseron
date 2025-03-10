"""Viseron types."""

import enum
from typing import Literal

SupportedDomains = Literal[
    "camera",
    "face_recognition",
    "image_classification",
    "license_plate_recognition",
    "motion_detector",
    "nvr",
    "object_detector",
]


class SnapshotDomain(enum.Enum):
    """Snapshot domains."""

    FACE_RECOGNITION = "face_recognition"
    LICENSE_PLATE_RECOGNITION = "license_plate_recognition"
    MOTION_DETECTOR = "motion_detector"
    OBJECT_DETECTOR = "object_detector"


DatabaseOperations = Literal["insert", "update", "delete"]
