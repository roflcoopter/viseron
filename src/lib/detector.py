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

    def filter_objects(self, obj, camera_config):
        if not obj["label"] in camera_config.object_detection.tracked_labels:
            return False

        for tracked_label in camera_config.object_detection.labels:
            if (
                tracked_label.label == obj["label"]
                and obj["confidence"] > tracked_label.confidence
                and tracked_label.height_min
                <= obj["height"]
                <= tracked_label.height_max
                and tracked_label.width_min <= obj["width"] <= tracked_label.width_max
            ):
                return True
        return False

    def object_detection(self, detector_queue):
        while True:
            filtered_objects = []

            frame = detector_queue.get()
            object_event = frame["object_event"]

            objects = self.ObjectDetection.return_objects(frame)

            if objects:
                LOGGER.debug(objects)

            filtered_objects = list(
                filter(
                    lambda obj: self.filter_objects(obj, frame["camera_config"]),
                    objects,
                )
            )

            if filtered_objects:
                pop_if_full(
                    frame["object_return_queue"],
                    {
                        "frame": frame["frame"],
                        "full_frame": frame["full_frame"],
                        "objects": filtered_objects,
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
