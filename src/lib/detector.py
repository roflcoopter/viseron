import importlib
import logging
from threading import Lock

import cv2
from voluptuous import Any, Optional, Required

from lib.config.config_logging import LoggingConfig
from lib.config.config_object_detection import SCHEMA as BASE_SCEHMA
from lib.helpers import calculate_relative_coords, pop_if_full

LOGGER = logging.getLogger(__name__)

SCHEMA = BASE_SCEHMA.extend(
    {
        Required("type"): str,
        Optional("model_width", default=None): Any(int, None),
        Optional("model_height", default=None): Any(int, None),
    }
)


class DetectedObject:
    """Object that holds a detected object. All coordinates and metrics are relative
    to make it easier to do calculations on different image resolutions"""

    def __init__(
        self, label, confidence, x1, y1, x2, y2, relative=True, model_res=None
    ):
        self._label = label
        self._confidence = round(float(confidence), 3)
        if relative:
            self._rel_x1 = float(round(x1, 3))
            self._rel_y1 = float(round(y1, 3))
            self._rel_x2 = float(round(x2, 3))
            self._rel_y2 = float(round(y2, 3))
        else:
            (
                self._rel_x1,
                self._rel_y1,
                self._rel_x2,
                self._rel_y2,
            ) = calculate_relative_coords((x1, y1, x2, y2), model_res)

        self._rel_width = float(round(self._rel_x2 - self._rel_x1, 3))
        self._rel_height = float(round(self._rel_y2 - self._rel_y1, 3))
        self._relevant = False

    @property
    def label(self):
        return self._label

    @property
    def confidence(self):
        return self._confidence

    @property
    def rel_width(self):
        return self._rel_width

    @property
    def rel_height(self):
        return self._rel_height

    @property
    def rel_x1(self):
        return self._rel_x1

    @property
    def rel_y1(self):
        return self._rel_y1

    @property
    def rel_x2(self):
        return self._rel_x2

    @property
    def rel_y2(self):
        return self._rel_y2

    @property
    def formatted(self):
        payload = {}
        payload["label"] = self.label
        payload["confidence"] = self.confidence
        payload["rel_width"] = self.rel_width
        payload["rel_height"] = self.rel_height
        payload["rel_x1"] = self.rel_x1
        payload["rel_y1"] = self.rel_y1
        payload["rel_x2"] = self.rel_x2
        payload["rel_y2"] = self.rel_y2
        return payload

    @property
    def relevant(self):
        """Returns if object is relevant, which means it passed through all filters"""
        return self._relevant

    @relevant.setter
    def relevant(self, value):
        self._relevant = value


class Detector:
    def __init__(self, object_detection_config):
        detector = importlib.import_module(
            "lib.detectors." + object_detection_config["type"]
        )
        config = detector.Config(detector.SCHEMA(object_detection_config))
        if getattr(config.logging, "level", None):
            LOGGER.setLevel(config.logging.level)

        LOGGER.debug(f"Initializing object detector {object_detection_config['type']}")

        self.config = config
        self.detection_lock = Lock()

        # Activate OpenCL
        if cv2.ocl.haveOpenCL():
            LOGGER.debug("OpenCL activated")
            cv2.ocl.setUseOpenCL(True)

        self.object_detector = detector.ObjectDetection(config)
        LOGGER.debug("Object detector initialized")

    def object_detection(self, detector_queue):
        while True:
            frame = detector_queue.get()
            self.detection_lock.acquire()
            frame["frame"].objects = self.object_detector.return_objects(frame)
            self.detection_lock.release()
            pop_if_full(
                frame["object_return_queue"], frame,
            )

    @property
    def model_width(self):
        return (
            self.config.model_width
            if self.config.model_width
            else self.object_detector.model_width
        )

    @property
    def model_height(self):
        return (
            self.config.model_height
            if self.config.model_height
            else self.object_detector.model_height
        )


class DetectorConfig:
    def __init__(self, object_detection):
        self._model_path = object_detection["model_path"]
        self._label_path = object_detection["label_path"]
        self._model_width = object_detection["model_width"]
        self._model_height = object_detection["model_height"]
        self._logging = None
        if object_detection.get("logging", None):
            self._logging = LoggingConfig(object_detection["logging"])

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
    def logging(self):
        return self._logging
