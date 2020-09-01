# https://github.com/iArunava/YOLOv3-Object-Detection-with-OpenCV
import configparser
import logging

import cv2
from lib.helpers import calculate_relative_coords

LOGGER = logging.getLogger(__name__)


class ObjectDetection:
    def __init__(
        self,
        model,
        model_config,
        label_path,
        nms,
        backend,
        target,
        model_width=None,
        model_height=None,
    ):
        self.nms = nms

        # Activate OpenCL
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)

        self.load_labels(label_path)
        self.load_network(model, model_config, backend, target)

        if model_width and model_height:
            self._model_width = model_width
            self._model_height = model_height
        else:
            config = configparser.ConfigParser(strict=False)
            config.read(model_config)
            self._model_width = int(config.get("net", "width"))
            self._model_height = int(config.get("net", "height"))

        self.model = cv2.dnn_DetectionModel(self.net)
        self.model.setInputParams(
            size=(self.model_width, self.model_height), scale=1 / 255
        )

    def load_labels(self, labels):
        # Load names of labels
        self.labels = None
        if labels:
            with open(labels, "rt") as labels_file:
                self.labels = labels_file.read().rstrip("\n").split("\n")

    def load_network(self, model, model_config, backend, target):
        # Load a network
        self.net = cv2.dnn.readNet(model, model_config, "darknet")
        self.net.setPreferableBackend(backend)
        self.net.setPreferableTarget(target)

    def post_process(self, labels, confidences, boxes):
        detections = []
        for (label, confidence, box) in zip(labels, confidences, boxes):
            relative_coords = calculate_relative_coords(
                (box[0], box[1], box[0] + box[2], box[1] + box[3]), self.model_res
            )

            detections.append(
                {
                    "label": self.labels[int(label[0])],
                    "confidence": round(confidence[0], 3),
                    "height": round(relative_coords[3] - relative_coords[1], 3),
                    "width": round(relative_coords[2] - relative_coords[0], 3),
                    "relative_x1": round(relative_coords[0], 3),
                    "relative_y1": round(relative_coords[1], 3),
                    "relative_x2": round(relative_coords[2], 3),
                    "relative_y2": round(relative_coords[3], 3),
                }
            )

        return detections

    def return_objects(self, frame):
        labels, confidences, boxes = self.model.detect(
            frame["frame"],
            frame["camera_config"].object_detection.min_confidence,
            self.nms,
        )

        objects = self.post_process(labels, confidences, boxes)
        return objects

    @property
    def model_width(self):
        return self._model_width

    @property
    def model_height(self):
        return self._model_height

    @property
    def model_res(self):
        return self.model_width, self.model_height
