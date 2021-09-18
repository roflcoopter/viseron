"""Background subtractor motion detection config."""
from voluptuous import All, Any, Coerce, Optional, Range

from viseron.motion import AbstractMotionDetectionConfig

from .const import ALPHA, AREA, THRESHOLD

SCHEMA = AbstractMotionDetectionConfig.SCHEMA.extend(
    {
        Optional("area", default=AREA): All(
            Any(All(float, Range(min=0.0, max=1.0)), 1, 0),
            Coerce(float),
        ),
        Optional("threshold", default=THRESHOLD): All(int, Range(min=0, max=255)),
        Optional("alpha", default=ALPHA): All(
            Any(All(float, Range(min=0.0, max=1.0)), 1, 0),
            Coerce(float),
        ),
    }
)


class Config(AbstractMotionDetectionConfig):
    """Config class."""

    def __init__(self, motion_config):
        super().__init__(motion_config)
        self._area = motion_config["area"]
        self._threshold = motion_config["threshold"]
        self._alpha = motion_config["alpha"]

    @property
    def area(self):
        """Return minimum area size allowed for motion detection."""
        return self._area

    @property
    def threshold(self):
        """Return threshold used in cv2.threshold."""
        return self._threshold

    @property
    def alpha(self):
        """Return alpha used in cv2.accumulateWeighted."""
        return self._alpha
