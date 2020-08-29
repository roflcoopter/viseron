import logging
import os
from typing import Union

from const import (
    ENV_CUDA_SUPPORTED,
    ENV_OPENCL_SUPPORTED,
    ENV_RASPBERRYPI3,
    DARKNET_DEFAULTS,
    EDGETPU_DEFAULTS,
)
from cv2.dnn import (
    DNN_BACKEND_CUDA,
    DNN_BACKEND_DEFAULT,
    DNN_BACKEND_OPENCV,
    DNN_TARGET_CPU,
    DNN_TARGET_CUDA,
    DNN_TARGET_OPENCL,
)
from voluptuous import (
    All,
    Any,
    Coerce,
    Invalid,
    Length,
    Optional,
    Range,
    Required,
    Schema,
)

LOGGER = logging.getLogger(__name__)


def ensure_min_max(detector: dict) -> dict:
    if detector["height_min"] > detector["height_max"]:
        raise Invalid("height_min may not be larger than height_max")
    if detector["width_min"] > detector["width_max"]:
        raise Invalid("width_min may not be larger than width_max")
    return detector


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


def get_detector_type(detector: str) -> str:
    if detector:
        return detector

    if (
        os.getenv(ENV_OPENCL_SUPPORTED) == "true"
        or os.getenv(ENV_CUDA_SUPPORTED) == "true"
    ):
        return DARKNET_DEFAULTS["type"]
    if os.getenv(ENV_RASPBERRYPI3) == "true":
        return EDGETPU_DEFAULTS["type"]
    return DARKNET_DEFAULTS["type"]


def get_model_path(model_path: str) -> str:
    if model_path:
        return model_path

    if (
        os.getenv(ENV_OPENCL_SUPPORTED) == "true"
        or os.getenv(ENV_CUDA_SUPPORTED) == "true"
    ):
        return DARKNET_DEFAULTS["model_path"]
    if os.getenv(ENV_RASPBERRYPI3) == "true":
        return EDGETPU_DEFAULTS["model_path"]
    return DARKNET_DEFAULTS["model_path"]


def get_model_config(model_config: str) -> Union[str, None]:
    if model_config:
        return model_config

    if (
        os.getenv(ENV_OPENCL_SUPPORTED) == "true"
        or os.getenv(ENV_CUDA_SUPPORTED) == "true"
    ):
        return DARKNET_DEFAULTS["model_config"]
    if os.getenv(ENV_RASPBERRYPI3) == "true":
        return None
    return DARKNET_DEFAULTS["model_config"]


def get_label_path(label_path: str) -> str:
    if label_path:
        return label_path

    if (
        os.getenv(ENV_OPENCL_SUPPORTED) == "true"
        or os.getenv(ENV_CUDA_SUPPORTED) == "true"
    ):
        return DARKNET_DEFAULTS["label_path"]
    if os.getenv(ENV_RASPBERRYPI3) == "true":
        return EDGETPU_DEFAULTS["label_path"]
    return DARKNET_DEFAULTS["label_path"]


LABELS_SCHEMA = Schema([str])

# TODO make schema easier by importing the relevant type and extracting defaults
SCHEMA = Schema(
    All(
        {
            Required("type"): All(
                get_detector_type, Any("darknet", "edgetpu", "posenet")
            ),
            Required("model_path"): All(get_model_path, str),
            Required("model_config", default=None): All(
                get_model_config, Any(str, None)
            ),
            Required("label_path"): All(get_label_path, str, Length(min=1)),
            Optional("model_width", default=None): Any(int, None),
            Optional("model_height", default=None): Any(int, None),
            Optional("interval", default=1): int,
            Optional("threshold", default=0.9): All(
                Any(0, 1, All(float, Range(min=0.0, max=1.0))), Coerce(float)
            ),
            Optional("suppression", default=0.4): All(
                Any(0, 1, All(float, Range(min=0, max=1))), Coerce(float)
            ),
            Optional("height_min", default=0.0): float,
            Optional("height_max", default=1.0): float,
            Optional("width_min", default=0.0): float,
            Optional("width_max", default=1.0): float,
            Optional("labels", default=["person"]): LABELS_SCHEMA,
        },
        ensure_min_max,
        # TODO Add this back
        # ensure_label,
    )
)


class ObjectDetectionConfig:
    schema = SCHEMA

    def __init__(self, object_detection):
        self._type = object_detection.type
        self._model_path = object_detection.model_path
        self._model_config = object_detection.model_config
        self._label_path = object_detection.label_path
        self._model_width = object_detection.model_width
        self._model_height = object_detection.model_height
        self._interval = object_detection.interval
        self._threshold = object_detection.threshold
        self._suppression = object_detection.suppression
        self._height_min = object_detection.height_min
        self._height_max = object_detection.height_max
        self._width_min = object_detection.width_min
        self._width_max = object_detection.width_max
        self._labels = object_detection.labels

    @property
    def type(self):
        return self._type

    @property
    def model_path(self):
        return self._model_path

    @property
    def model_config(self):
        return self._model_config

    @property
    def label_path(self):
        return self._label_path

    @property
    def model_width(self):
        return self._model_width

    @property
    def model_height(self):
        return self._model_height

    @property
    def interval(self):
        return self._interval

    @property
    def threshold(self):
        return self._threshold

    @property
    def suppression(self):
        return self._suppression

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
    def labels(self):
        return self._labels

    @property
    def dnn_preferable_backend(self):
        if os.getenv(ENV_CUDA_SUPPORTED) == "true":
            return DNN_BACKEND_CUDA
        if os.getenv(ENV_OPENCL_SUPPORTED) == "true":
            return DNN_BACKEND_OPENCV
        return DNN_BACKEND_DEFAULT

    @property
    def dnn_preferable_target(self):
        if os.getenv(ENV_CUDA_SUPPORTED) == "true":
            return DNN_TARGET_CUDA
        if os.getenv(ENV_OPENCL_SUPPORTED) == "true":
            return DNN_TARGET_OPENCL
        return DNN_TARGET_CPU
