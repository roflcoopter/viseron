"""Camera tuning modules."""

from .base import BaseTuningHandler
from .camera import CameraTuningHandler
from .face_recognition import FaceRecognitionTuningHandler
from .license_plate_recognition import LicensePlateRecognitionTuningHandler
from .motion_detector import MotionDetectorTuningHandler
from .object_detector import ObjectDetectorTuningHandler
from .onvif import OnvifTuningHandler

__all__ = [
    "BaseTuningHandler",
    "CameraTuningHandler",
    "FaceRecognitionTuningHandler",
    "LicensePlateRecognitionTuningHandler",
    "MotionDetectorTuningHandler",
    "ObjectDetectorTuningHandler",
    "OnvifTuningHandler",
]
