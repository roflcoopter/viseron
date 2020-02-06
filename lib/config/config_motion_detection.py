import logging

from voluptuous import (
    Required,
    Schema,
    Optional,
)

LOGGER = logging.getLogger(__name__)

DEFAULTS = {
    "interval": 0,
    "trigger": False,
    "timeout": False,
    "width": 0,
    "height": 0,
    "area": 0,
    "frames": 0,
}

SCHEMA = Schema(
    {
        Required("interval"): int,
        Optional("trigger", default=True): bool,
        Optional("timeout", default=True): bool,
        Required("width"): int,
        Required("height"): int,
        Required("area"): int,
        Required("frames"): int,
    }
)


class MotionDetectionConfig:
    schema = SCHEMA
    defaults = DEFAULTS

    def __init__(self, motion_detection):
        self._interval = motion_detection.interval
        self._trigger = motion_detection.trigger
        self._timeout = motion_detection.timeout
        self._width = motion_detection.width
        self._height = motion_detection.height
        self._area = motion_detection.area
        self._frames = motion_detection.frames

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

