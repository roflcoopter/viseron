import logging

import cv2
from lib.helpers import calculate_relative_coords, pop_if_full

LOGGER = logging.getLogger(__name__)


class DetectedObject:
    """Object that holds a detected object. All coordinates and metrics are relative
    to make it easier to do calculations on different image resolutions"""

    def __init__(
        self, label, confidence, x1, y1, x2, y2, relative=True, model_res=None
    ):
        self._label = label
        self._confidence = round(confidence, 3)
        if relative:
            self._rel_x1 = round(x1, 3)
            self._rel_y1 = round(y1, 3)
            self._rel_x2 = round(x2, 3)
            self._rel_y2 = round(y2, 3)
        else:
            (
                self._rel_x1,
                self._rel_y1,
                self._rel_x2,
                self._rel_y2,
            ) = calculate_relative_coords((x1, y1, x2, y2), model_res)

        self._rel_width = round(self._rel_x2 - self._rel_x1, 3)
        self._rel_height = round(self._rel_y2 - self._rel_y1, 3)
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
        payload["rel_y2"] = self._rel_y2
        return payload

    @property
    def relevant(self):
        """Returns if object is relevant, which means it passed through all filters"""
        return self._relevant

    @relevant.setter
    def relevant(self, value):
        self._relevant = value


class Detector:
    def __init__(self, config):
        LOGGER.info("Initializing detection thread")
        if getattr(config.object_detection.logging, "level", None):
            LOGGER.setLevel(config.object_detection.logging.level)

        self.config = config

        # Activate OpenCL
        if cv2.ocl.haveOpenCL():
            LOGGER.debug("OpenCL activated")
            cv2.ocl.setUseOpenCL(True)

        if self.config.object_detection.type == "edgetpu":
            from lib.edgetpu_detection import ObjectDetection

            self.ObjectDetection = ObjectDetection(
                model=self.config.object_detection.model_path,
                label_path=self.config.object_detection.label_path,
            )
        elif self.config.object_detection.type == "darknet":
            from lib.darknet_detection import ObjectDetection

            self.ObjectDetection = ObjectDetection(
                model=self.config.object_detection.model_path,
                model_config=self.config.object_detection.model_config,
                label_path=self.config.object_detection.label_path,
                nms=self.config.object_detection.suppression,
                backend=self.config.object_detection.dnn_preferable_backend,
                target=self.config.object_detection.dnn_preferable_target,
                model_width=self.config.object_detection.model_width,
                model_height=self.config.object_detection.model_height,
            )
        else:
            LOGGER.error("Could not import the correct detector")
            return

    def object_detection(self, detector_queue):
        while True:
            frame = detector_queue.get()
            frame["frame"].objects = self.ObjectDetection.return_objects(frame)
            pop_if_full(
                frame["object_return_queue"], frame,
            )

    @property
    def model_width(self):
        return (
            self.config.object_detection.model_width
            if self.config.object_detection.model_width
            else self.ObjectDetection.model_width
        )

    @property
    def model_height(self):
        return (
            self.config.object_detection.model_height
            if self.config.object_detection.model_height
            else self.ObjectDetection.model_height
        )

    def stop(self):
        return
