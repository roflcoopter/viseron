"""EdgeTPU object detection."""
from __future__ import annotations

import ast
import logging
import multiprocessing as mp
import subprocess as sp
import threading
from abc import abstractmethod
from queue import Queue

import voluptuous as vol

from viseron import Viseron
from viseron.domains import OptionalDomain, RequireDomain, setup_domain
from viseron.domains.image_classification import (
    BASE_CONFIG_SCHEMA as IMAGE_CLASSIFICATION_BASE_CONFIG_SCHEMA,
    ImageClassificationResult,
)
from viseron.domains.motion_detector.const import DOMAIN as MOTION_DETECTOR_DOMAIN
from viseron.domains.object_detector import BASE_CONFIG_SCHEMA
from viseron.domains.object_detector.const import CONFIG_CAMERAS
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.exceptions import ViseronError
from viseron.helpers import pop_if_full
from viseron.helpers.subprocess_worker import SubProcessWorker
from viseron.helpers.validators import Maybe
from viseron.watchdog.subprocess_watchdog import RestartablePopen

from .config import DeviceValidator, get_label_schema
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
    DEFAULT_MODEL_PATH,
    DESC_COMPONENT,
    DESC_DEVICE,
    DESC_IMAGE_CLASSIFICATION,
    DESC_MODEL_PATH,
    DESC_OBJECT_DETECTOR,
    DEVICE_CPU,
)

LOGGER = logging.getLogger(__name__)


EDGETPU_SCHEMA = {
    vol.Optional(
        CONFIG_MODEL_PATH,
        default=DEFAULT_MODEL_PATH,
        description=DESC_MODEL_PATH,
    ): Maybe(str),
    vol.Optional(
        CONFIG_DEVICE, default=DEFAULT_DEVICE, description=DESC_DEVICE
    ): vol.Any(DeviceValidator(), [DeviceValidator()]),
}


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): vol.Schema(
            {
                vol.Optional(
                    CONFIG_OBJECT_DETECTOR, description=DESC_OBJECT_DETECTOR
                ): BASE_CONFIG_SCHEMA.extend(
                    {**EDGETPU_SCHEMA, **get_label_schema(CONFIG_OBJECT_DETECTOR)}
                ),
                vol.Optional(
                    CONFIG_IMAGE_CLASSIFICATION, description=DESC_IMAGE_CLASSIFICATION
                ): IMAGE_CLASSIFICATION_BASE_CONFIG_SCHEMA.extend(
                    {**EDGETPU_SCHEMA, **get_label_schema(CONFIG_IMAGE_CLASSIFICATION)}
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config) -> bool:
    """Set up the edgetpu component."""
    LOGGER.debug(f"Available devices: {available_devices()}")
    config = config[COMPONENT]
    vis.data[COMPONENT] = {}

    if config.get(CONFIG_OBJECT_DETECTOR, None):
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
                optional_domains=[
                    OptionalDomain(
                        domain=MOTION_DETECTOR_DOMAIN,
                        identifier=camera_identifier,
                    ),
                ],
            )
    return True


def available_devices():
    """Get available devices by running list_edge_tpus in python3.9."""
    try:
        result = sp.run(
            [
                "python3.9",
                "-c",
                "from pycoral.utils.edgetpu import list_edge_tpus;"
                "print(list_edge_tpus())",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return ast.literal_eval(result.stdout)
    except Exception as error:
        LOGGER.error(f"Failed to get available devices: {error}")
        raise error


def read_label_file(file_path):
    """Read label file by running read_label_file in python3.9 using Popen."""
    try:
        result = sp.run(
            [
                "python3.9",
                "-c",
                (
                    f"from pycoral.utils.dataset import read_label_file; "
                    f"print(read_label_file('{file_path}'))"
                ),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return ast.literal_eval(result.stdout)
    except Exception as error:
        LOGGER.error(f"Failed to read label file: {error}")
        raise error


def get_available_devices():
    """Get available devices by running list_edge_tpus in python3.9 using Popen."""
    try:
        result = sp.run(
            [
                "python3.9",
                "-c",
                (
                    "from pycoral.utils.edgetpu import list_edge_tpus; "
                    "print(list_edge_tpus())"
                ),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return ast.literal_eval(result.stdout)
    except Exception as error:
        LOGGER.error(f"Failed to get available devices: {error}")
        raise error


def get_model_size(process_queue: Queue):
    """Get model size by sending a job to the subprocess."""
    process_queue.put("get_model_size")


def get_default_device(device):
    """Get default device based on what's available.

    Returns user configured device if it has been set.
    """
    if device:
        return device

    _available_devices = get_available_devices()
    if _available_devices:
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


class MakeInterpreterError(ViseronError):
    """Error raised on all failures to make interpreter."""


class EdgeTPU(SubProcessWorker):
    """EdgeTPU interface."""

    def __init__(self, vis, config, domain) -> None:
        self._config = config
        self._domain = domain
        self._device = get_default_device(config[CONFIG_DEVICE])
        self._model = get_default_model(domain, config[CONFIG_MODEL_PATH], self._device)
        self.labels = read_label_file(config[CONFIG_LABEL_PATH])

        LOGGER.debug(
            f"Loading interpreter with device {self._device}, model {self._model}"
        )
        LOGGER.debug(f"Using labels from {config[CONFIG_LABEL_PATH]}")

        self._result_queues: dict[str, Queue] = {}
        self._process_initialization_done = mp.Event()
        self._process_initialization_error = mp.Event()
        self._reload_lock = threading.Lock()
        self._consecutive_failures = 0
        super().__init__(vis, f"{COMPONENT}.{domain}")
        self.initialize()

    def initialize(self) -> None:
        """Initialize EdgeTPU."""
        self._process_initialization_done.wait(30)
        if (
            not self._process_initialization_done.is_set()
            or self._process_initialization_error.is_set()
        ):
            LOGGER.error("Failed to load EdgeTPU in subprocess")
            self.stop()
            raise MakeInterpreterError

        self._model_size_event = mp.Event()
        self._model_width = 0
        self._model_height = 0
        get_model_size(self._process_queue)
        self._model_size_event.wait(10)
        if not self._model_size_event.is_set():
            LOGGER.error("Failed to get model size")
            self.stop()
            raise MakeInterpreterError("Failed to get model size")

    @abstractmethod
    def post_process(self, item):
        """Post process after invoke."""

    def reload_if_needed(self):
        """Reload the interpreter if it fails 10 times in a row."""
        with self._reload_lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= 10:
                try:
                    LOGGER.warning(
                        "Reloading EdgeTPU interpreter after "
                        f"{self._consecutive_failures} consecutive failures."
                    )
                    self.stop()
                    self.start()
                except Exception as e:  # pylint: disable=broad-except
                    LOGGER.error(f"Failed to reload EdgeTPU interpreter: {e}")
                finally:
                    self._consecutive_failures = 0

    def spawn_subprocess(self) -> RestartablePopen:
        """Spawn subprocess."""
        device = self._device
        if isinstance(device, list):
            device = ",".join(device)
        return RestartablePopen(
            (
                "python3.9 -u viseron/components/edgetpu/edgetpu_subprocess.py "
                f"--manager-port {self._server_port} "
                f"--manager-authkey {self._authkey_store.authkey} "
                f"--device {device} "
                f"--model {self._model} "
                f"--model-type {self._domain} "
                f"--loglevel DEBUG"
            ).split(" "),
            name=self.subprocess_name,
            stdout=self._log_pipe,
            stderr=self._log_pipe,
        )

    def invoke(
        self, frame, camera_identifier, result_queue, frame_resolution: tuple[int, int]
    ):
        """Invoke interpreter."""
        self._result_queues[camera_identifier] = result_queue
        pop_if_full(
            self.input_queue,
            {
                "frame": frame,
                "camera_identifier": camera_identifier,
                "frame_resolution": frame_resolution,
            },
        )
        item = result_queue.get()
        return item["result"]

    def work_output(self, item) -> None:
        """Put result into queue."""
        if item == "init_done":
            self._process_initialization_done.set()
            LOGGER.debug("EdgeTPU initialized")
            return

        if item == "init_failed":
            LOGGER.error("Failed to initialize EdgeTPU")
            self._process_initialization_error.set()
            self._process_initialization_done.set()
            return

        if item.get("get_model_size", None):
            self._model_width = item["get_model_size"]["model_width"]
            self._model_height = item["get_model_size"]["model_height"]
            self._model_size_event.set()
            return

        self.post_process(item)
        pop_if_full(self._result_queues[item["camera_identifier"]], item)

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

    def post_process(self, item):
        """Post process detections."""
        processed_objects = []
        for obj in item["result"]:
            processed_objects.append(
                DetectedObject.from_absolute(
                    self.labels.get(obj["label"], obj["label"]),
                    float(obj["score"]),
                    obj["bbox"]["xmin"],
                    obj["bbox"]["ymin"],
                    obj["bbox"]["xmax"],
                    obj["bbox"]["ymax"],
                    frame_res=item["frame_resolution"],
                    model_res=(self.model_width, self.model_height),
                )
            )
        item["result"] = processed_objects


class EdgeTPUClassification(EdgeTPU):
    """EdgeTPU image classification interface."""

    def post_process(self, item) -> None:
        """Post process classifications."""
        processed_classes = []
        for classification in item["result"]:
            processed_classes.append(
                ImageClassificationResult(
                    item["camera_identifier"],
                    self.labels.get(
                        classification["label"], int(classification["label"])
                    ),
                    classification["score"],
                )
            )
        item["result"] = processed_classes
