"""Viseron types."""

from __future__ import annotations

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


class Domain(str, enum.Enum):
    """Domains."""

    CAMERA = "camera"
    FACE_RECOGNITION = "face_recognition"
    IMAGE_CLASSIFICATION = "image_classification"
    LICENSE_PLATE_RECOGNITION = "license_plate_recognition"
    MOTION_DETECTOR = "motion_detector"
    NVR = "nvr"
    OBJECT_DETECTOR = "object_detector"

    @classmethod
    def post_processors(
        cls,
    ) -> tuple[
        Literal[Domain.FACE_RECOGNITION],
        Literal[Domain.IMAGE_CLASSIFICATION],
        Literal[Domain.LICENSE_PLATE_RECOGNITION],
    ]:
        """Return post processors."""
        return (
            cls.FACE_RECOGNITION,
            cls.IMAGE_CLASSIFICATION,
            cls.LICENSE_PLATE_RECOGNITION,
        )


class SnapshotDomain(enum.Enum):
    """Snapshot domains."""

    FACE_RECOGNITION = "face_recognition"
    LICENSE_PLATE_RECOGNITION = "license_plate_recognition"
    MOTION_DETECTOR = "motion_detector"
    OBJECT_DETECTOR = "object_detector"


DatabaseOperations = Literal["insert", "update", "delete"]
