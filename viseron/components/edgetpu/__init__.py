"""EdgeTPU object detection."""
import logging
import re
from abc import abstractmethod

import tflite_runtime.interpreter as tflite
import voluptuous as vol
from pycoral.adapters import classify, common, detect
from pycoral.utils.dataset import read_label_file
from pycoral.utils.edgetpu import list_edge_tpus, make_interpreter

from viseron import Viseron
from viseron.domains import RequireDomain, setup_domain
from viseron.domains.image_classification import (
    BASE_CONFIG_SCHEMA as IMAGE_CLASSIFICATION_BASE_CONFIG_SCHEMA,
    ImageClassificationResult,
)
from viseron.domains.object_detector import BASE_CONFIG_SCHEMA
from viseron.domains.object_detector.const import CONFIG_CAMERAS
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.exceptions import ComponentNotReady
from viseron.helpers import pop_if_full
from viseron.helpers.child_process_worker import ChildProcessWorker

from .const import (
    COMPONENT,
    CONFIG_DEVICE,
    CONFIG_IMAGE_CLASSIFICATION,
    CONFIG_LABEL_PATH,
    CONFIG_MODEL_PATH,
    CONFIG_OBJECT_DETECTOR,
    DEFAULT_CLASSIFIER_CPU_MODEL,
    DEFAULT_CLASSIFIER_EDGETPU_MODEL,
    DEFAULT_DETECTOR_CPU_MODEL,
    DEFAULT_DETECTOR_EDGETPU_MODEL,
    DEFAULT_DEVICE,
    DEFAULT_LABEL_PATH,
    DEFAULT_LABEL_PATH_MAP,
    DEFAULT_MODEL_PATH,
    DEVICE_CPU,
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


class DefaultLabelPath:
    """Return default label path for specified domain."""

    def __init__(self, domain, msg=None):
        self.msg = msg
        self.domain = domain

    def __call__(self, value):
        """Return default label path for specified domain."""
        if value:
            return value
        return DEFAULT_LABEL_PATH_MAP[self.domain]


def get_label_schema(domain):
    """Return domain specific schema."""
    return {
        vol.Optional(CONFIG_LABEL_PATH, default=DEFAULT_LABEL_PATH): vol.All(
            vol.Maybe(str), DefaultLabelPath(domain)
        )
    }


EDGETPU_SCHEMA = {
    vol.Optional(CONFIG_MODEL_PATH, default=DEFAULT_MODEL_PATH): vol.Maybe(str),
    vol.Optional(CONFIG_DEVICE, default=DEFAULT_DEVICE): vol.Maybe(
        vol.All(str, edgetpu_device_validator)
    ),
}


CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT: vol.Schema(
            {
                vol.Optional(CONFIG_OBJECT_DETECTOR): BASE_CONFIG_SCHEMA.extend(
                    {**EDGETPU_SCHEMA, **get_label_schema(CONFIG_OBJECT_DETECTOR)}
                ),
                vol.Optional(
                    CONFIG_IMAGE_CLASSIFICATION
                ): IMAGE_CLASSIFICATION_BASE_CONFIG_SCHEMA.extend(
                    {**EDGETPU_SCHEMA, **get_label_schema(CONFIG_IMAGE_CLASSIFICATION)}
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config):
    """Set up the edgetpu component."""
    LOGGER.debug(f"Available devices: {list_edge_tpus()}")
    config = config[COMPONENT]
    vis.data[COMPONENT] = {}

    if config.get(CONFIG_OBJECT_DETECTOR, None):
        vis.data[COMPONENT][CONFIG_OBJECT_DETECTOR] = EdgeTPUDetection(
            vis, config[CONFIG_OBJECT_DETECTOR], CONFIG_OBJECT_DETECTOR
        )
        for camera_identifier in config[CONFIG_OBJECT_DETECTOR][CONFIG_CAMERAS].keys():
            setup_domain(
                vis,
                COMPONENT,
                CONFIG_OBJECT_DETECTOR,
                config,
                identifier=camera_identifier,
                require_domains=[
                    RequireDomain(
                        domain="camera",
                        identifier=camera_identifier,
                    )
                ],
            )
    if config.get(CONFIG_IMAGE_CLASSIFICATION, None):
        vis.data[COMPONENT][CONFIG_IMAGE_CLASSIFICATION] = EdgeTPUClassification(
            vis, config[CONFIG_IMAGE_CLASSIFICATION], CONFIG_IMAGE_CLASSIFICATION
        )
        for camera_identifier in config[CONFIG_IMAGE_CLASSIFICATION][
            CONFIG_CAMERAS
        ].keys():
            setup_domain(
                vis,
                COMPONENT,
                CONFIG_IMAGE_CLASSIFICATION,
                config,
                identifier=camera_identifier,
                require_domains=[
                    RequireDomain(
                        domain="camera",
                        identifier=camera_identifier,
                    )
                ],
            )
    return True


def get_default_device(device):
    """Get default device based on what's available.

    Returns user configured device if it has been set.
    """
    if device:
        return device

    available_devices = list_edge_tpus()
    if available_devices:
        return ":0"
    return DEVICE_CPU


def get_default_model(domain, model, device):
    """Get default model based on chosen device.

    Returns user configured model if it has been set.
    """
    if model:
        return model

    if domain == CONFIG_OBJECT_DETECTOR:
        if device == DEVICE_CPU:
            return DEFAULT_DETECTOR_CPU_MODEL
        return DEFAULT_DETECTOR_EDGETPU_MODEL

    if domain == CONFIG_IMAGE_CLASSIFICATION:
        if device == DEVICE_CPU:
            return DEFAULT_CLASSIFIER_CPU_MODEL
        return DEFAULT_CLASSIFIER_EDGETPU_MODEL

    raise ValueError(f"Unsupported domain: {domain}")


class EdgeTPU(ChildProcessWorker):
    """EdgeTPU interface."""

    def __init__(self, vis, config, domain):
        self._config = config
        self._device = get_default_device(config[CONFIG_DEVICE])
        self._model = get_default_model(domain, config[CONFIG_MODEL_PATH], self._device)
        self.labels = read_label_file(config[CONFIG_LABEL_PATH])

        LOGGER.debug(
            f"Loading interpreter with device {self._device}, model {self._model}"
        )
        LOGGER.debug(f"Using labels from {config[CONFIG_LABEL_PATH]}")

        # Create an interpreter to get the model size
        interpreter = self.make_interpreter(self._device, self._model)
        self.tensor_input_details = interpreter.get_input_details()
        self._model_width = self.tensor_input_details[0]["shape"][1]
        self._model_height = self.tensor_input_details[0]["shape"][2]
        # Discard the interpreter to release the EdgeTPU
        # It is re-create inside the spawned child process in process_initialization
        del interpreter

        self.interpreter = None
        self._result_queues = {}
        super().__init__(vis, f"{COMPONENT}.{domain}")

    def make_interpreter(self, device, model):
        """Make interpreter."""
        if device == DEVICE_CPU:
            interpreter = tflite.Interpreter(
                model_path=model,
            )
        else:
            try:
                interpreter = make_interpreter(
                    model,
                    device=self._config[CONFIG_DEVICE],
                )
            except ValueError as error:
                LOGGER.error(f"Error when trying to load EdgeTPU: {error}")
                raise ComponentNotReady() from error
        interpreter.allocate_tensors()
        return interpreter

    def process_initialization(self):
        """Make interpreter inside the child process."""
        self.interpreter = self.make_interpreter(self._device, self._model)

    @abstractmethod
    def post_process(self, item):
        """Post process after invoke."""

    def work_input(self, item):
        """Perform object detection."""
        common.set_input(self.interpreter, item["frame"])
        self.interpreter.invoke()
        item["result"] = self.post_process(item)
        return item

    def work_output(self, item):
        """Put result into queue."""
        pop_if_full(self._result_queues[item["camera_identifier"]], item)

    def invoke(self, frame, camera_identifier, result_queue):
        """Invoke interpreter."""
        self._result_queues[camera_identifier] = result_queue
        pop_if_full(
            self.input_queue, {"frame": frame, "camera_identifier": camera_identifier}
        )
        item = result_queue.get()
        return item["result"]

    @property
    def model_width(self) -> int:
        """Return trained model width."""
        return self._model_width

    @property
    def model_height(self) -> int:
        """Return trained model height."""
        return self._model_height


class EdgeTPUDetection(EdgeTPU):
    """EdgeTPU object detector interface."""

    def post_process(self, _item):
        """Post process detections."""
        processed_objects = []
        objects = detect.get_objects(self.interpreter, 0.1)

        for obj in objects:
            processed_objects.append(
                DetectedObject(
                    self.labels.get(obj.id, obj.id),
                    float(obj.score),
                    obj.bbox.xmin,
                    obj.bbox.ymin,
                    obj.bbox.xmax,
                    obj.bbox.ymax,
                    relative=False,
                    image_res=(self.model_width, self.model_height),
                )
            )

        return processed_objects


class EdgeTPUClassification(EdgeTPU):
    """EdgeTPU image classification interface."""

    def post_process(self, item):
        """Post process classifications."""
        classifications = classify.get_classes(self.interpreter, top_k=1)
        for classification in classifications:
            return ImageClassificationResult(
                item["camera_identifier"],
                self.labels.get(classification.id, int(classification.id)),
                classification.score,
            )
        return None
