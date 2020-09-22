import logging

import numpy as np
from voluptuous import Optional, Schema

from .config_logging import SCHEMA as LOGGING_SCHEMA

LOGGER = logging.getLogger(__name__)

DEFAULTS = {
    "interval": 1,
    "trigger_detector": True,
    "timeout": True,
    "max_timeout": 30,
    "width": 300,
    "height": 300,
    "area": 0.1,
    "frames": 3,
}

SCHEMA = Schema(
    {
        Optional("interval", default=DEFAULTS["interval"]): int,
        Optional("trigger_detector", default=DEFAULTS["trigger_detector"]): bool,
        Optional("timeout", default=DEFAULTS["timeout"]): bool,
        Optional("max_timeout", default=DEFAULTS["timeout"]): int,
        Optional("width", default=DEFAULTS["width"]): int,
        Optional("height", default=DEFAULTS["height"]): int,
        Optional("area", default=DEFAULTS["area"]): float,
        Optional("frames", default=DEFAULTS["frames"]): int,
        Optional("logging"): LOGGING_SCHEMA,
    },
)


class MotionDetectionConfig:
    schema = SCHEMA
    defaults = DEFAULTS

    def __init__(self, motion_detection, camera_motion_detection):
        self._interval = getattr(
            camera_motion_detection, "interval", motion_detection.interval
        )
        self._trigger_detector = getattr(
            camera_motion_detection,
            "trigger_detector",
            motion_detection.trigger_detector,
        )
        self._timeout = getattr(
            camera_motion_detection, "timeout", motion_detection.timeout
        )
        self._max_timeout = getattr(
            camera_motion_detection, "max_timeout", motion_detection.max_timeout
        )
        self._width = getattr(camera_motion_detection, "width", motion_detection.width)
        self._height = getattr(
            camera_motion_detection, "height", motion_detection.height
        )
        self._area = getattr(camera_motion_detection, "area", motion_detection.area)
        self._frames = getattr(
            camera_motion_detection, "frames", motion_detection.frames
        )
        self._mask = self.generate_mask(getattr(camera_motion_detection, "mask", []))
        self._logging = getattr(
            camera_motion_detection,
            "logging",
            (getattr(motion_detection, "logging", None)),
        )

    @staticmethod
    def generate_mask(coordinates):
        mask = []
        for mask_coordinates in coordinates:
            point_list = []
            for point in getattr(mask_coordinates, "points"):
                point_list.append([getattr(point, "x"), getattr(point, "y")])
            mask.append(np.array(point_list))
        return mask

    @property
    def interval(self):
        return self._interval

    @property
    def trigger_detector(self):
        return self._trigger_detector

    @property
    def timeout(self):
        return self._timeout

    @property
    def max_timeout(self):
        return self._max_timeout

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def area(self):
        return self._area

    @property
    def frames(self):
        return self._frames

    @property
    def mask(self):
        return self._mask

    @property
    def logging(self):
        return self._logging
