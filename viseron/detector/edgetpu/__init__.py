"""EdgeTPU object detection."""
import logging
import re
from os import PathLike
from typing import List, Union

import numpy as np
import tflite_runtime.interpreter as tflite

# from pycoral.adapters import common, detect
# from pycoral.utils.dataset import read_label_file
from pycoral.utils.edgetpu import list_edge_tpus, make_interpreter
from voluptuous import All, Invalid, Maybe, Optional, Required

from viseron.camera.frame_decoder import FrameToScan
from viseron.detector import AbstractDetectorConfig, AbstractObjectDetection
from viseron.detector.detected_object import DetectedObject

from .defaults import DEVICE, LABEL_PATH, MODEL_HEIGHT, MODEL_PATH, MODEL_WIDTH

DEVICE_REGEXES = [
    re.compile(r"^:[0-9]$"),  # match ':<N>'
    re.compile(r"^(usb|pci|cpu)$"),  # match 'usb', 'pci' and 'cpu'
    re.compile(r"^(usb|pci):[0-9]$"),  # match 'usb:<N>' and 'pci:<N>'
]

LOGGER = logging.getLogger(__name__)


def edgetpu_device_validator(device):
    """Check for valid EdgeTPU device name.

    Valid values are:
        ":<N>" : Use N-th Edge TPU
        "usb" : Use any USB Edge TPU
        "usb:<N>" : Use N-th USB Edge TPU
        "pci" : Use any PCIe Edge TPU
        "pci:<N>" : Use N-th PCIe Edge TPU
        "cpu" : Run on the CPU
    """
    for regex in DEVICE_REGEXES:
        if regex.match(device):
            return device
    raise Invalid(
        f"EdgeTPU device {device} is invalid. Please check your configuration"
    )


SCHEMA = AbstractDetectorConfig.schema.extend(
    {
        Required("model_path", default=MODEL_PATH): str,
        Optional("model_width", default=MODEL_WIDTH): Maybe(int),
        Optional("model_height", default=MODEL_HEIGHT): Maybe(int),
        Required("label_path", default=LABEL_PATH): str,
        Optional("device", default=DEVICE): All(str, edgetpu_device_validator),
    }
)


class ObjectDetection(AbstractObjectDetection):
    """Performs object detection."""

    def __init__(self, config):
        self.labels = self.read_labels(config.label_path)
        LOGGER.debug(f"Available devices: {list_edge_tpus()}")
        LOGGER.debug(f"Loading interpreter with device {config.device}")

        if config.device == "cpu":
            self.interpreter = tflite.Interpreter(
                model_path="/detectors/models/edgetpu/cpu_model.tflite",
            )
        else:
            self.interpreter = make_interpreter(
                config.model_path,
                device=config.device,
            )

        self.interpreter.allocate_tensors()

        self.tensor_input_details = self.interpreter.get_input_details()
        self.tensor_output_details = self.interpreter.get_output_details()

        if config.model_width and config.model_height:
            self._model_width = config.model_width
            self._model_height = config.model_height
        else:
            self._model_width = self.tensor_input_details[0]["shape"][1]
            self._model_height = self.tensor_input_details[0]["shape"][2]

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

    def preprocess(self, frame_to_scan: FrameToScan):
        """Return preprocessed frame before performing object detection."""
        frame_to_scan.frame.resize(
            frame_to_scan.decoder_name,
            self._model_width,
            self._model_height,
        )
        frame = frame_to_scan.frame.get_resized_frame(frame_to_scan.decoder_name).get()
        frame_to_scan.frame.save_preprocessed_frame(
            frame_to_scan.decoder_name,
            frame.reshape(1, frame.shape[0], frame.shape[1], frame.shape[2]),
        )

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

    def return_objects(self, frame_to_scan: FrameToScan) -> List[DetectedObject]:
        """Perform object detection."""
        tensor = frame_to_scan.frame.get_preprocessed_frame(frame_to_scan.decoder_name)

        self.interpreter.set_tensor(self.tensor_input_details[0]["index"], tensor)
        self.interpreter.invoke()

        objects = self.post_process(
            frame_to_scan.camera_config.object_detection.min_confidence
        )
        return objects

    @property
    def model_width(self) -> int:
        """Return trained model width."""
        return self._model_width

    @property
    def model_height(self) -> int:
        """Return trained model height."""
        return self._model_height


class Config(AbstractDetectorConfig):
    """EdgeTPU object detection config."""

    def __init__(self, detector_config):
        super().__init__(detector_config)
        self._model_path = detector_config["model_path"]
        self._model_width = detector_config["model_width"]
        self._model_height = detector_config["model_height"]
        self._label_path = detector_config["label_path"]
        self._device = detector_config["device"]

    @property
    def model_path(self) -> PathLike:
        """Return path to object detection model."""
        return self._model_path

    @property
    def model_width(self) -> Union[int, None]:
        """Return width that images will be resized to before running detection."""
        return self._model_width

    @property
    def model_height(self) -> Union[int, None]:
        """Return height that images will be resized to before running detection."""
        return self._model_height

    @property
    def label_path(self) -> PathLike:
        """Return path to object detection labels."""
        return self._label_path

    @property
    def device(self) -> str:
        """Return EdgeTPU device."""
        return self._device
