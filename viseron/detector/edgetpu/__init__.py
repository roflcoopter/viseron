"""EdgeTPU object detection."""
import logging
import traceback

import numpy as np
import tflite_runtime.interpreter as tflite
from voluptuous import Required

from viseron.detector import SCHEMA, DetectorConfig
from viseron.detector.detected_object import DetectedObject

from .defaults import LABEL_PATH, MODEL_PATH

LOGGER = logging.getLogger(__name__)

SCHEMA = SCHEMA.extend(
    {
        Required("model_path", default=MODEL_PATH): str,
        Required("label_path", default=LABEL_PATH): str,
    }
)


class ObjectDetection:
    """Performs object detection."""

    def __init__(self, config):
        self.labels = self.read_labels(config.label_path)
        try:
            self.interpreter = tflite.Interpreter(
                model_path=config.model_path,
                experimental_delegates=[
                    tflite.load_delegate("libedgetpu.so.1", {"device": "usb"})
                ],
            )
            LOGGER.debug("Using USB EdgeTPU")
        except ValueError:
            try:
                self.interpreter = tflite.Interpreter(
                    model_path=config.model_path,
                    experimental_delegates=[
                        tflite.load_delegate("libedgetpu.so.1", {"device": "pci:0"})
                    ],
                )
                LOGGER.debug("Using PCIe EdgeTPU")
            except ValueError as error:
                LOGGER.error("EdgeTPU not found. Detection will run on CPU")
                LOGGER.debug(f"Error when trying to load EdgeTPU: {error}")
                self.interpreter = tflite.Interpreter(
                    model_path="/detectors/models/edgetpu/cpu_model.tflite",
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
        with open(file_path, "r") as label_file:
            lines = label_file.readlines()
        labels = {}
        for line in lines:
            pair = line.strip().split(maxsplit=1)
            labels[int(pair[0])] = pair[1].strip()
        return labels

    @staticmethod
    def pre_process(frame):
        """Return preprocessed frame before performing object detection."""
        # This should be moved to decoder for speed
        frame = frame.get()
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

    def return_objects(self, frame):
        """Perform object detection."""
        tensor = self.pre_process(
            frame["frame"].get_resized_frame(frame["decoder_name"])
        )

        self.interpreter.set_tensor(self.tensor_input_details[0]["index"], tensor)
        self.interpreter.invoke()

        objects = self.post_process(
            frame["camera_config"].object_detection.min_confidence
        )
        return objects

    @property
    def model_width(self):
        """Return trained model width."""
        return self._model_width

    @property
    def model_height(self):
        """Return trained model height."""
        return self._model_height


class Config(DetectorConfig):
    """EdgeTPU object detection config."""
