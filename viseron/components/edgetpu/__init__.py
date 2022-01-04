"""EdgeTPU object detection."""
import logging
import re

import numpy as np
import tflite_runtime.interpreter as tflite
import voluptuous as vol
from pycoral.utils.edgetpu import list_edge_tpus, make_interpreter

from viseron import Viseron
from viseron.domains import setup_domain
from viseron.domains.object_detector import BASE_CONFIG_SCHEMA
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.helpers import pop_if_full
from viseron.helpers.child_process_worker import ChildProcessWorker

from .const import (
    COMPONENT,
    CONFIG_DEVICE,
    CONFIG_LABEL_PATH,
    CONFIG_MODEL_PATH,
    CONFIG_OBJECT_DETECTOR,
    DEFAULT_DEVICE,
    DEFAULT_LABEL_PATH,
    DEFAULT_MODEL_PATH,
)

LOGGER = logging.getLogger(__name__)


DEVICE_REGEXES = [
    re.compile(r"^:[0-9]$"),  # match ':<N>'
    re.compile(r"^(usb|pci|cpu)$"),  # match 'usb', 'pci' and 'cpu'
    re.compile(r"^(usb|pci):[0-9]$"),  # match 'usb:<N>' and 'pci:<N>'
]


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
    raise vol.Invalid(
        f"EdgeTPU device {device} is invalid. Please check your configuration"
    )


CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT: vol.Schema(
            {
                vol.Required(CONFIG_OBJECT_DETECTOR): BASE_CONFIG_SCHEMA.extend(
                    {
                        vol.Optional(
                            CONFIG_MODEL_PATH, default=DEFAULT_MODEL_PATH
                        ): str,
                        vol.Optional(
                            CONFIG_LABEL_PATH, default=DEFAULT_LABEL_PATH
                        ): str,
                        vol.Optional(CONFIG_DEVICE, default=DEFAULT_DEVICE): vol.All(
                            str, edgetpu_device_validator
                        ),
                    }
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config):
    """Set up the edgetpu component."""
    config = config[COMPONENT]
    vis.data[COMPONENT] = EdgeTPU(vis, config[CONFIG_OBJECT_DETECTOR])
    for domain in config.keys():
        setup_domain(vis, COMPONENT, domain, config)

    return True


class EdgeTPU(ChildProcessWorker):
    """EdgeTPU object detector interface."""

    def __init__(self, vis, config):
        self.labels = self.read_labels(config[CONFIG_LABEL_PATH])
        LOGGER.debug(f"Available devices: {list_edge_tpus()}")
        LOGGER.debug(f"Loading interpreter with device {config[CONFIG_DEVICE]}")

        if config[CONFIG_DEVICE] == "cpu":
            self.interpreter = tflite.Interpreter(
                model_path="/detectors/models/edgetpu/mobiledet_cpu_model.tflite",
            )
        else:
            self.interpreter = make_interpreter(
                config[CONFIG_MODEL_PATH],
                device=config[CONFIG_DEVICE],
            )
        self.interpreter.allocate_tensors()

        self.tensor_input_details = self.interpreter.get_input_details()
        self._model_width = self.tensor_input_details[0]["shape"][1]
        self._model_height = self.tensor_input_details[0]["shape"][2]

        self._result_queues = {}

        super().__init__(vis, COMPONENT)

    @staticmethod
    def read_labels(file_path):
        """Read labels from file."""
        with open(file_path, "rt", encoding="utf-8") as labels_file:
            return labels_file.read().rstrip("\n").split("\n")

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

    def work_input(self, item):
        """Perform object detection."""
        self.interpreter.set_tensor(
            self.tensor_input_details[0]["index"], item["frame"]
        )
        self.interpreter.invoke()
        item["objects"] = self.post_process(0.1)
        return item

    def work_output(self, item):
        """Put result into queue."""
        pop_if_full(self._result_queues[item["camera_identifier"]], item)

    def invoke(self, frame, camera_identifier, object_result_queue):
        """Invoke interpreter."""
        self._result_queues[camera_identifier] = object_result_queue
        pop_if_full(
            self.input_queue, {"frame": frame, "camera_identifier": camera_identifier}
        )
        item = object_result_queue.get()
        return item["objects"]

    @property
    def model_width(self) -> int:
        """Return trained model width."""
        return self._model_width

    @property
    def model_height(self) -> int:
        """Return trained model height."""
        return self._model_height
