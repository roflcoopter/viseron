import logging

from voluptuous import All, Any, Invalid, Length, Range, Required, Schema, Coerce

LOGGER = logging.getLogger(__name__)


def ensure_min_max(detector: dict) -> dict:
    if detector["height_min"] > detector["height_max"]:
        raise Invalid("height_min may not be larger than height_max")
    if detector["width_min"] > detector["width_max"]:
        raise Invalid("width_min may not be larger than width_max")
    return detector


LABELS_SCHEMA = Schema([str])

SCHEMA = Schema(
    All(
        {
            Required("type"): Any("darknet", "edgetpu", "posenet"),
            Required("model_path"): str,
            Required("model_config", default=None): Any(str, None),
            Required("label_path", default=None): Any(All(str, Length(min=1)), None),
            Required("model_width"): int,
            Required("model_height"): int,
            Required("interval", default=1): int,
            Required("threshold"): All(
                Any(0, 1, All(float, Range(min=0.0, max=1.0))), Coerce(float)
            ),
            Required("suppression"): All(
                Any(0, 1, All(float, Range(min=0, max=1))), Coerce(float)
            ),
            Required("height_min"): float,
            Required("height_max"): float,
            Required("width_min"): float,
            Required("width_max"): float,
            Required("labels"): LABELS_SCHEMA,
        },
        ensure_min_max,
        # TODO ADD THIS BACK
        # ensure_label,
    )
)


class ObjectDetectionConfig:
    schema = SCHEMA

    def __init__(self, object_detection):
        self._type = object_detection.type
        self._model_path = object_detection.model_path
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
