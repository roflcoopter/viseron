"""Background Subtractor MOG2 motion detection config."""
from voluptuous import All, Any, Coerce, Optional, Range

from viseron.motion import AbstractMotionDetectionConfig

from .const import AREA, DETECT_SHADOWS, HISTORY, LEARNING_RATE, THRESHOLD

SCHEMA = AbstractMotionDetectionConfig.SCHEMA.extend(
    {
        Optional("area", default=AREA): All(
            Any(
                All(
                    float,
                    Range(min=0.0, max=1.0),
                ),
                1,
                0,
            ),
            Coerce(float),
        ),
        Optional("threshold", default=THRESHOLD): All(int, Range(min=0, max=255)),
        Optional("history", default=HISTORY): int,
        Optional("detect_shadows", default=DETECT_SHADOWS): bool,
        Optional("learning_rate", default=LEARNING_RATE): All(
            Any(
                All(
                    float,
                    Range(min=0.0, max=1.0),
                ),
                1,
                0,
                -1,
            ),
            Coerce(float),
        ),
    }
)


class Config(AbstractMotionDetectionConfig):
    """Background Subtractor MOG2 config."""

    def __init__(self, motion_config):
        super().__init__(motion_config)
        self._area = motion_config["area"]
        self._threshold = motion_config["threshold"]
        self._history = motion_config["history"]
        self._detect_shadows = motion_config["detect_shadows"]
        self._learning_rate = motion_config["learning_rate"]

    @property
    def area(self) -> float:
        """Return minimum area size allowed for motion detection."""
        return self._area

    @property
    def threshold(self) -> int:
        """Return threshold."""
        return self._threshold

    @property
    def history(self) -> int:
        """Return length of history."""
        return self._history

    @property
    def detect_shadows(self) -> bool:
        """Return if shadows should be detected."""
        return self._detect_shadows

    @property
    def learning_rate(self) -> float:
        """Return the learning rate."""
        return self._learning_rate
