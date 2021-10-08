"""Darknet object detector."""
import configparser
import logging

import cv2

from viseron.camera.frame_decoder import FrameToScan
from viseron.detector import AbstractObjectDetection, Detector
from viseron.detector.detected_object import DetectedObject

from .config import Config

LOGGER = logging.getLogger(__name__)


class ObjectDetection(AbstractObjectDetection):
    """Performs object detection."""

    def __init__(self, config: Config):
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
            with open(labels, "rt", encoding="utf-8") as labels_file:
                self.labels = labels_file.read().rstrip("\n").split("\n")

    def load_network(self, model, model_config, backend, target):
        """Load network."""
        # Load a network
        self.net = cv2.dnn.readNet(model, model_config, "darknet")
        self.net.setPreferableBackend(backend)
        self.net.setPreferableTarget(target)

    def preprocess(self, frame_to_scan: FrameToScan):
        """Preprocess frame before detection."""
        frame_to_scan.frame.resize(
            frame_to_scan.decoder_name,
            self._model_width,
            self._model_height,
        )
        frame_to_scan.frame.save_preprocessed_frame(
            frame_to_scan.decoder_name,
            frame_to_scan.frame.get_resized_frame(frame_to_scan.decoder_name),
        )

    def post_process(self, labels, confidences, boxes):
        """Post process detections."""
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
                    image_res=self.model_res,
                )
            )

        return detections

    def return_objects(self, frame_to_scan: FrameToScan):
        """Perform object detection.

        Running detection using CUDA at the exact same time as running sp.Popen causes
        the detection process to hang and return the same results infinitely.
        Therefore we acquire a lock before inference and sp.Popen to avoid this.
        """
        with Detector.lock:
            labels, confidences, boxes = self.model.detect(
                frame_to_scan.frame.get_preprocessed_frame(frame_to_scan.decoder_name),
                frame_to_scan.camera_config.object_detection.min_confidence,
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
