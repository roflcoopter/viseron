"""Viseron types."""

from typing import Literal

SupportedDomains = Literal[
    "camera",
    "face_recognition",
    "image_classification",
    "motion_detector",
    "nvr",
    "object_detector",
]
