"""Motion detection config."""
from voluptuous import All, Any, Coerce, Optional, Range, Required, Schema

from viseron.helpers import generate_mask

from .config_logging import SCHEMA as LOGGING_SCHEMA, LoggingConfig

DEFAULTS = {
    "interval": 1,
    "trigger_detector": True,
    "trigger_recorder": False,
    "timeout": True,
    "max_timeout": 30,
    "width": 300,
    "height": 300,
    "frames": 3,
}

SCHEMA = Schema(
    {
        Required("type"): str,
        Optional("interval", default=DEFAULTS["interval"]): All(
            Any(float, int), Coerce(float), Range(min=0.0)
        ),
        Optional("trigger_detector", default=DEFAULTS["trigger_detector"]): bool,
        Optional("trigger_recorder", default=DEFAULTS["trigger_recorder"]): bool,
        Optional("timeout", default=DEFAULTS["timeout"]): bool,
        Optional("max_timeout", default=DEFAULTS["max_timeout"]): int,
        Optional("width", default=DEFAULTS["width"]): int,
        Optional("height", default=DEFAULTS["height"]): int,
        Optional("frames", default=DEFAULTS["frames"]): int,
        Optional("mask", default=[]): [
            {
                Required("points"): [
                    {
                        Required("x"): int,
                        Required("y"): int,
                    }
                ],
            }
        ],
        Optional("logging"): LOGGING_SCHEMA,
    },
)


class MotionDetectionConfig:
    """Motion detection config.

    All motion detector config classes must inherit from this one.
    """

    schema = SCHEMA

    def __init__(self, motion_config):
        self._type = motion_config["type"]
        self._interval = motion_config["interval"]
        self._trigger_detector = motion_config["trigger_detector"]
        self._trigger_recorder = motion_config["trigger_recorder"]
        self._timeout = motion_config["timeout"]
        self._max_timeout = motion_config["max_timeout"]
        self._width = motion_config["width"]
        self._height = motion_config["height"]
        self._frames = motion_config["frames"]
        self._mask = generate_mask(motion_config["mask"])
        logging = motion_config.get("logging", None)
        self._logging = LoggingConfig(logging) if logging else None

    @property
    def type(self) -> str:
        """Return detector type."""
        return self._type

    @property
    def interval(self):
        """Return interval."""
        return self._interval

    @property
    def trigger_detector(self):
        """Return if motion triggers detector."""
        return self._trigger_detector

    @property
    def trigger_recorder(self):
        """Return if motion starts the recorder."""
        return self._trigger_recorder

    @property
    def timeout(self):
        """Return motion timeout."""
        return self._timeout

    @property
    def max_timeout(self):
        """Return max motion timeout."""
        return self._max_timeout

    @property
    def width(self):
        """Return the width every frame will be resized to before detection."""
        return self._width

    @property
    def height(self):
        """Return the height every frame will be resized to before detection."""
        return self._height

    @property
    def frames(self):
        """Return number of consecutive frames before motion is considered detected."""
        return self._frames

    @property
    def mask(self):
        """Return mask."""
        return self._mask

    @property
    def logging(self):
        """Return logging config."""
        return self._logging
