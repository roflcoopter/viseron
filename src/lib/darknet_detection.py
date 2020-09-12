# https://github.com/iArunava/YOLOv3-Object-Detection-with-OpenCV
import configparser
import logging

import cv2
from lib.detector import DetectedObject

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
            detections.append(
                DetectedObject(
                    self.labels[int(label[0])],
                    confidence[0],
                    box[0],
                    box[1],
                    box[0] + box[2],
                    box[1] + box[3],
                    relative=False,
                    model_res=self.model_res,
                )
            )

        return detections

    def return_objects(self, frame):
        labels, confidences, boxes = self.model.detect(
            frame["frame"].get_resized_frame(frame["decoder_name"]),
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
