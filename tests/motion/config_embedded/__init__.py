"""Dummy module that has Config embedded."""
from viseron.motion import AbstractMotionDetection, AbstractMotionDetectionConfig

SCHEMA = "Testing"


class MotionDetection(AbstractMotionDetection):
    """Dummy module that has Config embedded."""

    pass


class Config(AbstractMotionDetectionConfig):
    """Dummy module that has Config embedded."""

    pass
