"""Viseron types."""

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

DatabaseOperations = Literal["insert", "update", "delete"]
