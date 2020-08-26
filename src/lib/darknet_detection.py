# https://github.com/iArunava/YOLOv3-Object-Detection-with-OpenCV
import configparser
import logging

import cv2 as cv
import numpy as np
from lib.helpers import calculate_relative_coords

LOGGER = logging.getLogger(__name__)


class ObjectDetection:
    def __init__(
        self,
        model,
        model_config,
        classes,
        thr,
        nms,
        backend,
        target,
        model_width=None,
        model_height=None,
    ):
        self.threshold = thr
        self.nms = nms

        # Activate OpenCL
        if cv.ocl.haveOpenCL():
            cv.ocl.setUseOpenCL(True)

        self.load_classes(classes)
        self.load_network(model, model_config, backend, target)

        if model_width and model_height:
            self._model_width = model_width
            self._model_height = model_height
        else:
            config = configparser.ConfigParser(strict=False)
            config.read(model_config)
            self._model_width = int(config.get("net", "width"))
            self._model_height = int(config.get("net", "height"))

    def load_classes(self, classes):
        # Load names of classes
        self.classes = None
        if classes:
            with open(classes, "rt") as labels_file:
                self.classes = labels_file.read().rstrip("\n").split("\n")

    def load_network(self, model, model_config, backend, target):
        # Load a network
        self.net = cv.dnn.readNet(model, model_config, "darknet")
        self.net.setPreferableBackend(backend)
        self.net.setPreferableTarget(target)

    def get_output_names(self, net):
        layer_names = net.getLayerNames()
        return [layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()]

    def postprocess(self, outs):
        classes = []
        confidences = []
        boxes = []
        for out in outs:
            for detection in out:
                scores = detection[5:]
                detected_class = np.argmax(scores)
                confidence = scores[detected_class]
                if confidence > self.threshold:
                    center_x = int(detection[0] * self.model_res[0])
                    center_y = int(detection[1] * self.model_res[1])
                    width = int(detection[2] * self.model_res[0])
                    height = int(detection[3] * self.model_res[1])
                    left = int(center_x - width / 2)
                    top = int(center_y - height / 2)
                    classes.append(detected_class)
                    confidences.append(float(confidence))
                    boxes.append([left, top, width, height])

        indices = cv.dnn.NMSBoxes(boxes, confidences, self.threshold, self.nms)

        detections = list()

        for i in indices:
            i = i[0]
            box = boxes[i]
            left = box[0]
            top = box[1]
            width = box[2]
            height = box[3]

            if self.classes:
                label = self.classes[classes[i]]

            relative_coords = calculate_relative_coords(
                (left, top, left + width, top + height), self.model_res
            )

            detections.append(
                {
                    "label": label if label else "Unknown",
                    "confidence": round(confidences[i], 3),
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
        # Create a 4D blob from a frame.
        blob = cv.dnn.blobFromImage(
            frame,
            0.00392,
            (self.model_width, self.model_height),
            [0, 0, 0],
            True,
            crop=False,
        )

        # Run a model
        self.net.setInput(blob)
        outs = self.net.forward(self.get_output_names(self.net))

        objects = self.postprocess(outs)

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
