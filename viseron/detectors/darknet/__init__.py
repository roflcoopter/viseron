"""Darknet object detector."""
import configparser
import logging
import os

import cv2
from cv2.dnn import (
    DNN_BACKEND_CUDA,
    DNN_BACKEND_DEFAULT,
    DNN_BACKEND_OPENCV,
    DNN_TARGET_CPU,
    DNN_TARGET_CUDA,
    DNN_TARGET_OPENCL,
)
from voluptuous import All, Any, Coerce, Optional, Range, Required

import viseron.detector as detector
from viseron.const import ENV_CUDA_SUPPORTED, ENV_OPENCL_SUPPORTED

from .defaults import LABEL_PATH, MODEL_CONFIG, MODEL_PATH

SCHEMA = detector.SCHEMA.extend(
    {
        Required("model_path", default=MODEL_PATH): str,
        Required("model_config", default=MODEL_CONFIG): str,
        Required("label_path", default=LABEL_PATH): str,
        Optional("suppression", default=0.4): All(
            Any(0, 1, All(float, Range(min=0.0, max=1.0))), Coerce(float)
        ),
    }
)

LOGGER = logging.getLogger(__name__)


class ObjectDetection:
    """Performs object detection."""

    def __init__(self, config):
        self.nms = config.suppression

        # Activate OpenCL
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)

        self.load_labels(config.label_path)
        self.load_network(
            config.model_path,
            config.model_config,
            config.dnn_preferable_backend,
            config.dnn_preferable_target,
        )

        if config.model_width and config.model_height:
            self._model_width = config.model_width
            self._model_height = config.model_height
        else:
            model_config = configparser.ConfigParser(strict=False)
            model_config.read(config.model_config)
            self._model_width = int(model_config.get("net", "width"))
            self._model_height = int(model_config.get("net", "height"))

        self.model = cv2.dnn_DetectionModel(self.net)
        self.model.setInputParams(
            size=(self.model_width, self.model_height), scale=1 / 255
        )

    def load_labels(self, labels):
        """Load labels from file."""
        # Load names of labels
        self.labels = None
        if labels:
            with open(labels, "rt") as labels_file:
                self.labels = labels_file.read().rstrip("\n").split("\n")

    def load_network(self, model, model_config, backend, target):
        """Load network."""
        # Load a network
        self.net = cv2.dnn.readNet(model, model_config, "darknet")
        self.net.setPreferableBackend(backend)
        self.net.setPreferableTarget(target)

    def post_process(self, labels, confidences, boxes):
        """Post process detections."""
        detections = []
        for (label, confidence, box) in zip(labels, confidences, boxes):
            detections.append(
                detector.DetectedObject(
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
        """Perform object detection."""
        labels, confidences, boxes = self.model.detect(
            frame["frame"].get_resized_frame(frame["decoder_name"]),
            frame["camera_config"].object_detection.min_confidence,
            self.nms,
        )

        objects = self.post_process(labels, confidences, boxes)
        return objects

    @property
    def model_width(self):
        """Return trained model width."""
        return self._model_width

    @property
    def model_height(self):
        """Return trained model height."""
        return self._model_height

    @property
    def model_res(self):
        """Return trained model resolution."""
        return self.model_width, self.model_height


class Config(detector.DetectorConfig):
    """Darknet object detection config."""

    def __init__(self, detector_config):
        super().__init__(detector_config)
        self._model_config = detector_config["model_config"]
        self._suppression = detector_config["suppression"]

    @property
    def model_config(self):
        """Return model config path."""
        return self._model_config

    @property
    def suppression(self):
        """Retun threshold for non maximum suppression."""
        return self._suppression

    @property
    def dnn_preferable_backend(self):
        """Return DNN backend."""
        if os.getenv(ENV_CUDA_SUPPORTED) == "true":
            return DNN_BACKEND_CUDA
        if os.getenv(ENV_OPENCL_SUPPORTED) == "true":
            return DNN_BACKEND_OPENCV
        return DNN_BACKEND_DEFAULT

    @property
    def dnn_preferable_target(self):
        """Return DNN target."""
        if os.getenv(ENV_CUDA_SUPPORTED) == "true":
            return DNN_TARGET_CUDA
        if os.getenv(ENV_OPENCL_SUPPORTED) == "true":
            return DNN_TARGET_OPENCL
        return DNN_TARGET_CPU
