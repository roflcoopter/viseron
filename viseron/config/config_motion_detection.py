import numpy as np
from voluptuous import All, Any, Coerce, Optional, Range, Schema

from .config_logging import SCHEMA as LOGGING_SCHEMA, LoggingConfig

DEFAULTS = {
    "interval": 1,
    "trigger_detector": True,
    "timeout": True,
    "max_timeout": 30,
    "width": 300,
    "height": 300,
    "area": 0.1,
    "threshold": 15,
    "alpha": 0.1,
    "frames": 3,
}

SCHEMA = Schema(
    {
        Optional("interval", default=DEFAULTS["interval"]): All(
            Any(float, int), Coerce(float), Range(min=0.0)
        ),
        Optional("trigger_detector", default=DEFAULTS["trigger_detector"]): bool,
        Optional("timeout", default=DEFAULTS["timeout"]): bool,
        Optional("max_timeout", default=DEFAULTS["max_timeout"]): int,
        Optional("width", default=DEFAULTS["width"]): int,
        Optional("height", default=DEFAULTS["height"]): int,
        Optional("area", default=DEFAULTS["area"]): All(
            Any(All(float, Range(min=0.0, max=1.0)), 1, 0),
            Coerce(float),
        ),
        Optional("threshold", default=DEFAULTS["threshold"]): All(
            int, Range(min=0, max=255)
        ),
        Optional("alpha", default=DEFAULTS["alpha"]): All(
            Any(All(float, Range(min=0.0, max=1.0)), 1, 0),
            Coerce(float),
        ),
        Optional("frames", default=DEFAULTS["frames"]): int,
        Optional("logging"): LOGGING_SCHEMA,
    },
)


class MotionDetectionConfig:
    schema = SCHEMA
    defaults = DEFAULTS

    def __init__(self, motion_detection, camera_motion_detection):
        self._interval = camera_motion_detection.get(
            "interval", motion_detection["interval"]
        )
        self._trigger_detector = camera_motion_detection.get(
            "trigger_detector",
            motion_detection["trigger_detector"],
        )
        self._timeout = camera_motion_detection.get(
            "timeout", motion_detection["timeout"]
        )
        self._max_timeout = camera_motion_detection.get(
            "max_timeout", motion_detection["max_timeout"]
        )
        self._width = camera_motion_detection.get("width", motion_detection["width"])
        self._height = camera_motion_detection.get("height", motion_detection["height"])
        self._area = camera_motion_detection.get("area", motion_detection["area"])
        self._threshold = camera_motion_detection.get(
            "threshold", motion_detection["threshold"]
        )
        self._alpha = camera_motion_detection.get("alpha", motion_detection["alpha"])
        self._frames = camera_motion_detection.get("frames", motion_detection["frames"])
        self._mask = self.generate_mask(camera_motion_detection.get("mask", []))
        logging = camera_motion_detection.get(
            "logging",
            (motion_detection.get("logging", None)),
        )
        self._logging = LoggingConfig(logging) if logging else logging

    @staticmethod
    def generate_mask(coordinates):
        mask = []
        for mask_coordinates in coordinates:
            point_list = []
            for point in mask_coordinates["points"]:
                point_list.append([point["x"], point["y"]])
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
    def threshold(self):
        return self._threshold

    @property
    def alpha(self):
        return self._alpha

    @property
    def frames(self):
        return self._frames

    @property
    def mask(self):
        return self._mask

    @property
    def logging(self):
        return self._logging
