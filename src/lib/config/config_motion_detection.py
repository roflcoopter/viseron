import logging

from voluptuous import Optional, Schema

from .config_logging import SCHEMA as LOGGING_SCHEMA

LOGGER = logging.getLogger(__name__)

DEFAULTS = {
    "interval": 1,
    "trigger": False,
    "timeout": False,
    "width": 300,
    "height": 300,
    "area": 6000,
    "frames": 3,
}

SCHEMA = Schema(
    {
        Optional("interval", default=DEFAULTS["interval"]): int,
        Optional("trigger", default=DEFAULTS["trigger"]): bool,
        Optional("timeout", default=DEFAULTS["timeout"]): bool,
        Optional("width", default=DEFAULTS["width"]): int,
        Optional("height", default=DEFAULTS["height"]): int,
        Optional("area", default=DEFAULTS["area"]): int,
        Optional("frames", default=DEFAULTS["frames"]): int,
        Optional("logging", default={}): LOGGING_SCHEMA,
    },
)


class MotionDetectionConfig:
    schema = SCHEMA
    defaults = DEFAULTS

    def __init__(self, motion_detection, camera_motion_detection):
        self._interval = getattr(
            camera_motion_detection, "interval", motion_detection.interval
        )
        self._trigger = getattr(
            camera_motion_detection, "trigger", motion_detection.trigger
        )
        self._timeout = getattr(
            camera_motion_detection, "timeout", motion_detection.timeout
        )
        self._width = getattr(camera_motion_detection, "width", motion_detection.width)
        self._height = getattr(
            camera_motion_detection, "height", motion_detection.height
        )
        self._area = getattr(camera_motion_detection, "area", motion_detection.area)
        self._frames = getattr(
            camera_motion_detection, "frames", motion_detection.frames
        )
        self._logging = getattr(
            camera_motion_detection, "logging", motion_detection.logging
        )

    @property
    def interval(self):
        return self._interval

    @property
    def trigger(self):
        return self._trigger

    @property
    def timeout(self):
        return self._timeout

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
    def logging(self):
        return self._logging
