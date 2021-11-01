"""EdgeTPU Object detector."""
import logging
from typing import List

import cv2
import numpy as np
import tflite_runtime.interpreter as tflite
from pycoral.utils.edgetpu import list_edge_tpus, make_interpreter

from viseron import Viseron
from viseron.domains.object_detector import AbstractObjectDetector
from viseron.domains.object_detector.detected_object import DetectedObject

from .const import COMPONENT, CONFIG_DEVICE, CONFIG_LABEL_PATH, CONFIG_MODEL_PATH

LOGGER = logging.getLogger(__name__)


class ObjectDetector(AbstractObjectDetector):
    """Performs object detection."""

    def __init__(self, vis: Viseron, config):
        self._vis = vis
        self.labels = self.read_labels(config[CONFIG_LABEL_PATH])
        LOGGER.debug(f"Available devices: {list_edge_tpus()}")
        LOGGER.debug(f"Loading interpreter with device {config[CONFIG_DEVICE]}")

        if config[CONFIG_DEVICE] == "cpu":
            self.interpreter = tflite.Interpreter(
                model_path="/detectors/models/edgetpu/cpu_model.tflite",
            )
        else:
            self.interpreter = make_interpreter(
                config[CONFIG_MODEL_PATH],
                device=config[CONFIG_DEVICE],
            )

        self.interpreter.allocate_tensors()

        self.tensor_input_details = self.interpreter.get_input_details()
        self.tensor_output_details = self.interpreter.get_output_details()
        self._model_width = self.tensor_input_details[0]["shape"][1]
        self._model_height = self.tensor_input_details[0]["shape"][2]

        super().__init__(vis, config)

        self._vis.register_object_detector(COMPONENT, self._input_queue)

    @staticmethod
    def read_labels(file_path):
        """Read labels from file."""
        with open(file_path, "r", encoding="utf-8") as label_file:
            lines = label_file.readlines()
        labels = {}
        for line in lines:
            pair = line.strip().split(maxsplit=1)
            labels[int(pair[0])] = pair[1].strip()
        return labels

    def preprocess(self, frame):
        """Return preprocessed frame before performing object detection."""
        frame = cv2.resize(
            frame,
            (self._model_width, self._model_height),
            interpolation=cv2.INTER_LINEAR,
        )

        return frame.reshape(1, frame.shape[0], frame.shape[1], frame.shape[2])

    def output_tensor(self, i):
        """Return output tensor view."""
        tensor = self.interpreter.tensor(
            self.interpreter.get_output_details()[i]["index"]
        )()
        return np.squeeze(tensor)

    def post_process(self, confidence):
        """Post process detections."""
        processed_objects = []
        boxes = self.output_tensor(0)
        labels = self.output_tensor(1)
        scores = self.output_tensor(2)
        count = int(self.output_tensor(3))

        for i in range(count):
            if float(scores[i]) > confidence:
                processed_objects.append(
                    DetectedObject(
                        self.labels[int(labels[i])],
                        float(scores[i]),
                        boxes[i][1],
                        boxes[i][0],
                        boxes[i][3],
                        boxes[i][2],
                    )
                )

        return processed_objects

    def return_objects(self, frame) -> List[DetectedObject]:
        """Perform object detection."""
        tensor = frame

        self.interpreter.set_tensor(self.tensor_input_details[0]["index"], tensor)
        self.interpreter.invoke()

        objects = self.post_process(0.1)
        return objects

    @property
    def name(self) -> str:
        """Return object detector name."""
        return COMPONENT

    @property
    def model_width(self) -> int:
        """Return trained model width."""
        return self._model_width

    @property
    def model_height(self) -> int:
        """Return trained model height."""
        return self._model_height
