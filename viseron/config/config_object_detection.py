import os

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

from .config_logging import SCHEMA as LOGGING_SCHEMA
from .config_logging import LoggingConfig


def ensure_min_max(label: dict) -> dict:
    if label["height_min"] > label["height_max"]:
        raise Invalid("height_min may not be larger than height_max")
    if label["width_min"] > label["width_max"]:
        raise Invalid("width_min may not be larger than width_max")
    return label


# TODO test this inside docker container
def ensure_label(detector: dict) -> dict:
    if detector["type"] in ["darknet", "edgetpu"] and detector["label_path"] is None:
        raise Invalid("Detector type {} requires a label file".format(detector["type"]))
    if detector["label_path"]:
        with open(detector["label_path"], "rt") as label_file:
            labels_file = label_file.read().rstrip("\n").split("\n")
        for label in detector["labels"]:
            if label not in labels_file:
                raise Invalid("Provided label doesn't exist in label file")
    return detector


def get_detector_type() -> str:
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
                Optional("triggers_recording", default=True): bool,
                Optional("require_motion", default=False): bool,
                Optional("post_processor", default=None): Any(str, None),
            },
            ensure_min_max,
        )
    ]
)

SCHEMA = Schema(
    {
        Optional("type", default=get_detector_type()): str,
        Optional("interval", default=1): All(
            Any(float, int), Coerce(float), Range(min=0.0)
        ),
        Optional("labels", default=[{"label": "person"}]): LABELS_SCHEMA,
        Optional("log_all_objects", default=False): bool,
        Optional("logging"): LOGGING_SCHEMA,
    },
    extra=ALLOW_EXTRA,
)


class LabelConfig:
    def __init__(self, label):
        self._label = label["label"]
        self._confidence = label["confidence"]
        self._height_min = label["height_min"]
        self._height_max = label["height_max"]
        self._width_min = label["width_min"]
        self._width_max = label["width_max"]
        self._triggers_recording = label["triggers_recording"]
        self._require_motion = label["require_motion"]
        self._post_processor = label["post_processor"]

    @property
    def label(self):
        return self._label

    @property
    def confidence(self):
        return self._confidence

    @property
    def height_min(self):
        return self._height_min

    @property
    def height_max(self):
        return self._height_max

    @property
    def width_min(self):
        return self._width_min

    @property
    def width_max(self):
        return self._width_max

    @property
    def triggers_recording(self):
        return self._triggers_recording

    @property
    def require_motion(self):
        return self._require_motion

    @property
    def post_processor(self):
        return self._post_processor


class ObjectDetectionConfig:
    schema = SCHEMA

    def __init__(self, object_detection, camera_object_detection, camera_zones):
        self._type = object_detection["type"]
        self._interval = camera_object_detection.get(
            "interval", object_detection["interval"]
        )
        self._labels = []
        for label in camera_object_detection.get("labels", object_detection["labels"]):
            self._labels.append(LabelConfig(label))

        self._log_all_objects = camera_object_detection.get(
            "log_all_objects", object_detection["log_all_objects"]
        )

        logging = camera_object_detection.get(
            "logging",
            (object_detection.get("logging", None)),
        )
        self._logging = LoggingConfig(logging) if logging else logging

        self._min_confidence = min(
            label.confidence for label in self.concat_labels(camera_zones)
        )

    def concat_labels(self, camera_zones):
        """Creates a concatenated list of global labels + all labels in each zone"""
        zone_labels = []
        for zone in camera_zones:
            zone_labels += zone["labels"]

        return self.labels + zone_labels

    @property
    def type(self):
        return self._type

    @property
    def interval(self):
        return self._interval

    @property
    def min_confidence(self):
        return self._min_confidence

    @property
    def labels(self):
        return self._labels

    @property
    def log_all_objects(self):
        return self._log_all_objects

    @property
    def logging(self):
        return self._logging
