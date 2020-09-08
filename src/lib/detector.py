import logging

import cv2
from lib.helpers import pop_if_full

LOGGER = logging.getLogger(__name__)


class Detector:
    def __init__(self, config):
        LOGGER.info("Initializing detection thread")
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
