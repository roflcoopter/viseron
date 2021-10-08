"""Dummy module that has Config embedded."""
from viseron.detector import AbstractDetectorConfig, AbstractObjectDetection

SCHEMA = "Testing"


class ObjectDetection(AbstractObjectDetection):
    """Dummy module that has Config embedded."""


class Config(AbstractDetectorConfig):
    """Dummy module that has Config embedded."""
