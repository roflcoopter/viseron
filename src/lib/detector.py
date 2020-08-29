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

        self.filtered_objects = []

        if self.config.object_detection.type == "edgetpu":
            from lib.edgetpu_detection import ObjectDetection

            self.ObjectDetection = ObjectDetection(
                model=self.config.object_detection.model_path,
                labels=self.config.object_detection.label_path,
                threshold=self.config.object_detection.threshold,
            )
        elif self.config.object_detection.type == "darknet":
            from lib.darknet_detection import ObjectDetection

            self.ObjectDetection = ObjectDetection(
                model=self.config.object_detection.model_path,
                model_config=self.config.object_detection.model_config,
                classes=self.config.object_detection.label_path,
                thr=self.config.object_detection.threshold,
                nms=self.config.object_detection.suppression,
                backend=self.config.object_detection.dnn_preferable_backend,
                target=self.config.object_detection.dnn_preferable_target,
                model_width=self.config.object_detection.model_width,
                model_height=self.config.object_detection.model_height,
            )
        else:
            LOGGER.error("OBJECT_DETECTION_TYPE has to be either edgetpu or darknet")
            return

    def filter_objects(self, result):
        if (
            result["label"] in self.config.object_detection.labels
            and self.config.object_detection.height_min
            <= result["height"]
            <= self.config.object_detection.height_max
            and self.config.object_detection.width_min
            <= result["width"]
            <= self.config.object_detection.width_max
        ):
            return True
        return False

    def object_detection(self, detector_queue):
        while True:
            self.filtered_objects = []

            frame = detector_queue.get()
            object_event = frame["object_event"]

            objects = self.ObjectDetection.return_objects(frame["frame"])

            if objects:
                LOGGER.debug(objects)

            self.filtered_objects = list(filter(self.filter_objects, objects))

            if self.filtered_objects:
                pop_if_full(
                    frame["object_return_queue"],
                    {
                        "frame": frame["frame"],
                        "full_frame": frame["full_frame"],
                        "objects": self.filtered_objects,
                    },
                )

                if not object_event.is_set():
                    object_event.set()
                continue

            if object_event.is_set():
                object_event.clear()

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
