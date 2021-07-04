"""Object Detection config."""
import os
from typing import List

from voluptuous import (
    ALLOW_EXTRA,
    All,
    Any,
    Coerce,
    Invalid,
    Optional,
    Range,
    Required,
    Schema,
)

from viseron.const import (
    ENV_CUDA_SUPPORTED,
    ENV_OPENCL_SUPPORTED,
    ENV_RASPBERRYPI3,
    ENV_RASPBERRYPI4,
)
from viseron.helpers import generate_mask
from viseron.helpers.validators import deprecated

from .config_logging import SCHEMA as LOGGING_SCHEMA, LoggingConfig


def ensure_min_max(label: dict) -> dict:
    """Ensure min values are not larger than max values."""
    if label["height_min"] >= label["height_max"]:
        raise Invalid("height_min may not be larger or equal to height_max")
    if label["width_min"] >= label["width_max"]:
        raise Invalid("width_min may not be larger or equal to width_max")
    return label


def get_detector_type() -> str:
    """Return default detector."""
    if (
        os.getenv(ENV_OPENCL_SUPPORTED) == "true"
        or os.getenv(ENV_CUDA_SUPPORTED) == "true"
    ):
        return "darknet"
    if os.getenv(ENV_RASPBERRYPI3) == "true":
        return "edgetpu"
    if os.getenv(ENV_RASPBERRYPI4) == "true":
        return "edgetpu"
    return "darknet"


LABELS_SCHEMA = Schema(
    [
        All(
            deprecated("triggers_recording", replacement="trigger_recorder"),
            {
                Required("label"): str,
                Optional("confidence", default=0.8): All(
                    Any(0, 1, All(float, Range(min=0.0, max=1.0))), Coerce(float)
                ),
                Optional("height_min", default=0.0): All(
                    Any(0, 1, All(float, Range(min=0.0, max=1.0))), Coerce(float)
                ),
                Optional("height_max", default=1.0): All(
                    Any(0, 1, All(float, Range(min=0.0, max=1.0))), Coerce(float)
                ),
                Optional("width_min", default=0.0): All(
                    Any(0, 1, All(float, Range(min=0.0, max=1.0))), Coerce(float)
                ),
                Optional("width_max", default=1.0): All(
                    Any(0, 1, All(float, Range(min=0.0, max=1.0))), Coerce(float)
                ),
                Optional("trigger_recorder", default=True): bool,
                Optional("require_motion", default=False): bool,
                Optional("post_processor", default=None): Any(str, None),
            },
            ensure_min_max,
        )
    ]
)


class LabelConfig:
    """Label config."""

    def __init__(self, label):
        self._label: str = label["label"]
        self._confidence: float = label["confidence"]
        self._height_min: float = label["height_min"]
        self._height_max: float = label["height_max"]
        self._width_min: float = label["width_min"]
        self._width_max: float = label["width_max"]
        self._trigger_recorder: bool = label["trigger_recorder"]
        self._require_motion: bool = label["require_motion"]
        self._post_processor: str = label["post_processor"]

    @property
    def label(self) -> str:
        """Return label name."""
        return self._label

    @property
    def confidence(self) -> float:
        """Return minimum confidence."""
        return self._confidence

    @property
    def height_min(self) -> float:
        """Return minimum height."""
        return self._height_min

    @property
    def height_max(self) -> float:
        """Return maximum height."""
        return self._height_max

    @property
    def width_min(self) -> float:
        """Return minimum width."""
        return self._width_min

    @property
    def width_max(self) -> float:
        """Return maximum width."""
        return self._width_max

    @property
    def trigger_recorder(self) -> bool:
        """Return if label triggers recorder."""
        return self._trigger_recorder

    @property
    def require_motion(self) -> bool:
        """Return if label requires motion to trigger recorder."""
        return self._require_motion

    @property
    def post_processor(self) -> str:
        """Return post processors."""
        return self._post_processor


# Allow extra during initial validation of config
SCHEMA = Schema(
    {
        Optional("type", default=get_detector_type()): str,
        Optional("enable", default=True): bool,
        Optional("interval", default=1): All(
            Any(float, int), Coerce(float), Range(min=0.0)
        ),
        Optional("labels", default=[{"label": "person"}]): LABELS_SCHEMA,
        Optional("log_all_objects", default=False): bool,
        Optional("logging"): LOGGING_SCHEMA,
    },
    extra=ALLOW_EXTRA,
)


class ObjectDetectionConfig:
    """Object detection config.

    All object detector config classes must inheritfrom this one.

    ALLOW_EXTRA is set in the base schema to allow each detector to have its own
    config options.
    PREVENT_EXTRA is added after the global config is validated.
    The config is validated again in the Detector class, but with each detectors
    unique schema.
    """

    schema = SCHEMA

    # pylint: disable=dangerous-default-value
    def __init__(self, object_detection, camera_object_detection={}, camera_zones={}):
        self._type = object_detection["type"]
        self._enable = camera_object_detection.get("enable", object_detection["enable"])
        self._interval = camera_object_detection.get(
            "interval", object_detection["interval"]
        )
        self._labels = []
        for label in camera_object_detection.get("labels", object_detection["labels"]):
            self._labels.append(LabelConfig(label))
        self._mask = generate_mask(camera_object_detection.get("mask", []))

        self._log_all_objects = camera_object_detection.get(
            "log_all_objects", object_detection["log_all_objects"]
        )

        logging = camera_object_detection.get(
            "logging",
            (object_detection.get("logging", None)),
        )
        self._logging = LoggingConfig(logging) if logging else logging

        self._min_confidence = min(
            (label.confidence for label in self.concat_labels(camera_zones)),
            default=1.0,
        )

    def concat_labels(self, camera_zones) -> List[LabelConfig]:
        """Return a concatenated list of global labels + all labels in each zone."""
        zone_labels = []
        for zone in camera_zones:
            zone_labels += zone["labels"]

        return self.labels + zone_labels

    @property
    def type(self) -> str:
        """Return detector type."""
        return self._type

    @property
    def enable(self) -> bool:
        """Return if detector is enabled."""
        return self._enable

    @property
    def interval(self) -> float:
        """Return interval."""
        return self._interval

    @property
    def min_confidence(self) -> float:
        """Return lowest configured confidence between all labels."""
        return self._min_confidence

    @property
    def labels(self) -> List[LabelConfig]:
        """Return label configs."""
        return self._labels

    @property
    def log_all_objects(self) -> bool:
        """Return if all labels should be logged, not only configured labels."""
        return self._log_all_objects

    @property
    def mask(self):
        """Return mask."""
        return self._mask

    @property
    def logging(self) -> LoggingConfig:
        """Return logging config."""
        return self._logging
