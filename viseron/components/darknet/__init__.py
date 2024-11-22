"""Darknet object detection."""
from __future__ import annotations

import configparser
import logging
import multiprocessing as mp
import os
import pwd
from abc import ABC, abstractmethod
from queue import Empty, Queue
from typing import Any

import cv2
import numpy as np
import voluptuous as vol

from viseron import Viseron
from viseron.const import ENV_CUDA_SUPPORTED, ENV_OPENCL_SUPPORTED
from viseron.domains import OptionalDomain, RequireDomain, setup_domain
from viseron.domains.motion_detector.const import DOMAIN as MOTION_DETECTOR_DOMAIN
from viseron.domains.object_detector import BASE_CONFIG_SCHEMA
from viseron.domains.object_detector.const import CONFIG_CAMERAS
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.exceptions import ComponentNotReady, ViseronError
from viseron.helpers import letterbox_resize, pop_if_full
from viseron.helpers.child_process_worker import ChildProcessWorker
from viseron.helpers.logs import CTypesLogPipe
from viseron.helpers.schemas import FLOAT_MIN_ZERO_MAX_ONE
from viseron.helpers.subprocess_worker import SubProcessWorker
from viseron.watchdog.subprocess_watchdog import RestartablePopen

from . import darknet
from .const import (
    COMPONENT,
    CONFIG_DNN_BACKEND,
    CONFIG_DNN_TARGET,
    CONFIG_HALF_PRECISION,
    CONFIG_LABEL_PATH,
    CONFIG_MODEL_CONFIG,
    CONFIG_MODEL_PATH,
    CONFIG_OBJECT_DETECTOR,
    CONFIG_SUPPRESSION,
    DEFAULT_DNN_BACKEND,
    DEFAULT_DNN_TARGET,
    DEFAULT_HALF_PRECISION,
    DEFAULT_LABEL_PATH,
    DEFAULT_MODEL_CONFIG,
    DEFAULT_MODEL_PATH,
    DEFAULT_SUPPRESSION,
    DESC_COMPONENT,
    DESC_DNN_BACKEND,
    DESC_DNN_TARGET,
    DESC_HALF_PRECISION,
    DESC_LABEL_PATH,
    DESC_MODEL_CONFIG,
    DESC_MODEL_PATH,
    DESC_OBJECT_DETECTOR,
    DESC_SUPPRESSION,
    DNN_BACKENDS,
    DNN_CPU,
    DNN_DEFAULT,
    DNN_OPENCL,
    DNN_OPENCV,
    DNN_TARGETS,
)

LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): vol.Schema(
            {
                vol.Required(
                    CONFIG_OBJECT_DETECTOR, description=DESC_OBJECT_DETECTOR
                ): BASE_CONFIG_SCHEMA.extend(
                    {
                        vol.Optional(
                            CONFIG_MODEL_PATH,
                            default=DEFAULT_MODEL_PATH,
                            description=DESC_MODEL_PATH,
                        ): str,
                        vol.Optional(
                            CONFIG_MODEL_CONFIG,
                            default=DEFAULT_MODEL_CONFIG,
                            description=DESC_MODEL_CONFIG,
                        ): str,
                        vol.Optional(
                            CONFIG_LABEL_PATH,
                            default=DEFAULT_LABEL_PATH,
                            description=DESC_LABEL_PATH,
                        ): str,
                        vol.Optional(
                            CONFIG_SUPPRESSION,
                            default=DEFAULT_SUPPRESSION,
                            description=DESC_SUPPRESSION,
                        ): FLOAT_MIN_ZERO_MAX_ONE,
                        vol.Optional(
                            CONFIG_DNN_BACKEND,
                            default=DEFAULT_DNN_BACKEND,
                            description=DESC_DNN_BACKEND,
                        ): vol.Maybe(vol.In(DNN_BACKENDS)),
                        vol.Optional(
                            CONFIG_DNN_TARGET,
                            default=DEFAULT_DNN_TARGET,
                            description=DESC_DNN_TARGET,
                        ): vol.Maybe(vol.In(DNN_TARGETS)),
                        vol.Optional(
                            CONFIG_HALF_PRECISION,
                            default=DEFAULT_HALF_PRECISION,
                            description=DESC_HALF_PRECISION,
                        ): bool,
                    }
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config: dict[str, Any]) -> bool:
    """Set up the darknet component."""
    config = config[COMPONENT]
    if (
        os.getenv(ENV_CUDA_SUPPORTED) == "true"
        and config[CONFIG_OBJECT_DETECTOR][CONFIG_DNN_BACKEND] is None
        and config[CONFIG_OBJECT_DETECTOR][CONFIG_DNN_TARGET] is None
    ):
        try:
            vis.data[COMPONENT] = DarknetNative(vis, config[CONFIG_OBJECT_DETECTOR])
        except LoadDarknetError as error:
            raise ComponentNotReady from error
    else:
        vis.data[COMPONENT] = DarknetDNN(vis, config[CONFIG_OBJECT_DETECTOR])

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
            optional_domains=[
                OptionalDomain(
                    domain=MOTION_DETECTOR_DOMAIN,
                    identifier=camera_identifier,
                ),
            ],
        )

    return True


class LoadDarknetError(ViseronError):
    """Raised when failing to load Darknet network."""


class BaseDarknet(ABC):
    """Base class for native Darknet and Darknet via OpenCV."""

    def __init__(
        self,
        vis: Viseron,
        config: dict[str, Any],
    ) -> None:
        self._vis = vis
        self._config = config

        model_config = configparser.ConfigParser(strict=False)
        model_config.read(config[CONFIG_MODEL_CONFIG])
        self._model_width = int(model_config.get("net", "width"))
        self._model_height = int(model_config.get("net", "height"))

        LOGGER.debug(
            f"Using weights {config[CONFIG_MODEL_PATH]} and "
            f"config {config[CONFIG_MODEL_CONFIG]}, "
            f"{self._model_width}x{self._model_height}"
        )

        self.labels = self.load_labels(config[CONFIG_LABEL_PATH])

        self._nms = config[CONFIG_SUPPRESSION]
        self._result_queues: dict[str, Queue] = {}

    def load_labels(self, labels: str) -> list[str]:
        """Load labels from file."""
        # Load names of labels
        with open(labels, encoding="utf-8") as labels_file:
            return labels_file.read().rstrip("\n").split("\n")

    @property
    def model_width(self) -> int:
        """Return trained model width."""
        return self._model_width

    @property
    def model_height(self) -> int:
        """Return trained model height."""
        return self._model_height

    @property
    def model_res(self):
        """Return trained model resolution."""
        return self.model_width, self.model_height

    @abstractmethod
    def preprocess(self, frame):
        """Pre process frame before detection."""

    @abstractmethod
    def detect(self, frame, camera_identifier, result_queue, min_confidence):
        """Perform detection."""

    @abstractmethod
    def post_process(self, detections, camera_resolution):
        """Post process detections."""


class DarknetDNNError(ViseronError):
    """Raised when failing to load Darknet in subprocess."""


class DarknetDNN(BaseDarknet, SubProcessWorker):
    """Darknet object detector interface."""

    def __init__(
        self,
        vis: Viseron,
        config: dict[str, Any],
    ) -> None:
        LOGGER.debug("Using OpenCV DNN Darknet")
        BaseDarknet.__init__(self, vis, config)
        self._process_initialization_done = mp.Event()
        self._process_initialization_error = mp.Event()
        SubProcessWorker.__init__(self, vis, f"{COMPONENT}.{CONFIG_OBJECT_DETECTOR}")

        if cv2.ocl.haveOpenCL():
            LOGGER.debug("Enabling OpenCL")
            cv2.ocl.setUseOpenCL(True)

        self._process_initialization_done.wait(10)
        if (
            not self._process_initialization_done.is_set()
            or self._process_initialization_error.is_set()
        ):
            LOGGER.error("Failed to load Darknet in subprocess")
            self.stop()
            raise DarknetDNNError("Failed to load Darknet in subprocess")

    def spawn_subprocess(self) -> RestartablePopen:
        """Spawn subprocess."""
        return RestartablePopen(
            (
                "python3 -u viseron/components/darknet/darknet_subprocess.py "
                f"--manager-port {self._server_port} "
                f"--manager-authkey {self._authkey_store.authkey} "
                f"--model-path={self._config[CONFIG_MODEL_PATH]} "
                f"--model-config={self._config[CONFIG_MODEL_CONFIG]} "
                f"--model-width={self.model_width} "
                f"--model-height={self.model_height} "
                f"--backend={self.dnn_preferable_backend} "
                f"--target={self.dnn_preferable_target} "
                f"--loglevel DEBUG"
            ).split(" "),
            name=self.subprocess_name,
            stdout=self._log_pipe,
            stderr=self._log_pipe,
        )

    def preprocess(self, frame) -> np.ndarray:
        """Pre process frame before detection."""
        return cv2.resize(
            frame,
            (self.model_width, self.model_height),
            interpolation=cv2.INTER_LINEAR,
        )

    def detect(self, frame, camera_identifier, result_queue, min_confidence):
        """Run detection on frame."""
        self._result_queues[camera_identifier] = result_queue
        pop_if_full(
            self.input_queue,
            {
                "frame": frame,
                "camera_identifier": camera_identifier,
                "min_confidence": min_confidence,
                "nms": self._nms,
            },
        )
        item = result_queue.get()
        return item["result"]

    def work_output(self, item) -> None:
        """Put result into queue."""
        if item == "init_done":
            self._process_initialization_done.set()
            LOGGER.debug("Darknet initialized")
            return

        if item == "init_failed":
            LOGGER.error("Failed to initialize Darknet")
            self._process_initialization_error.set()
            self._process_initialization_done.set()
            return
        pop_if_full(self._result_queues[item["camera_identifier"]], item)

    def post_process(self, detections, camera_resolution):
        """Post process detections."""
        _detections = []
        for (label, confidence, box) in zip(
            detections[0], detections[1], detections[2]
        ):
            _detections.append(
                DetectedObject.from_absolute(
                    self.labels[int(label)],
                    confidence,
                    box[0],
                    box[1],
                    box[0] + box[2],
                    box[1] + box[3],
                    frame_res=camera_resolution,
                    model_res=self.model_res,
                )
            )

        return _detections

    @property
    def dnn_preferable_backend(self) -> int:
        """Return DNN backend."""
        if self._config[CONFIG_DNN_BACKEND]:
            return DNN_BACKENDS[self._config[CONFIG_DNN_BACKEND]]
        if os.getenv(ENV_OPENCL_SUPPORTED) == "true":
            return DNN_BACKENDS[DNN_OPENCV]
        return DNN_BACKENDS[DNN_DEFAULT]

    @property
    def dnn_preferable_target(self) -> int:
        """Return DNN target."""
        if self._config[CONFIG_DNN_TARGET]:
            return DNN_TARGETS[self._config[CONFIG_DNN_TARGET]]
        if os.getenv(ENV_OPENCL_SUPPORTED) == "true":
            return DNN_TARGETS[DNN_OPENCL]
        return DNN_TARGETS[DNN_CPU]


class DarknetNative(BaseDarknet, ChildProcessWorker):
    """Darknet object detector interface using native Darknet.

    OpenCVs DNN bugs out when spawning subprocesses.
    This class is used when CUDA is available for this reason.
    See https://github.com/opencv/opencv/issues/19643
    """

    def __init__(
        self,
        vis: Viseron,
        config: dict[str, Any],
    ) -> None:
        LOGGER.debug("Using native Darknet")
        BaseDarknet.__init__(self, vis, config)

        self.create_data_file(config, self.labels)

        self._darknet = darknet.DarknetWrapper(config[CONFIG_HALF_PRECISION])
        self._network = None
        self._labels = None
        self._darknet_image = None

        self._process_initialization_done = mp.Event()
        ChildProcessWorker.__init__(self, vis, f"{COMPONENT}.{CONFIG_OBJECT_DETECTOR}")
        if not self._process_initialization_done.wait(timeout=15):
            raise LoadDarknetError("Failed to load Darknet network in child process")

    def create_data_file(self, config, labels) -> None:
        """Create Darknet datafile which describes the labels."""
        LOGGER.debug(f"Creating Darknet data file {self.darknet_data_path}")
        with open(self.darknet_data_path, "w", encoding="utf-8") as data_file:
            data_file.write(f"classes={len(labels)}\n")
            data_file.write(f"names={config[CONFIG_LABEL_PATH]}")

    def process_initialization(self) -> None:
        """Load network inside the child process."""
        self._darknet_image = self._darknet.make_image(
            self._model_width, self._model_height, 3
        )

        logger = logging.getLogger(f"{__name__}.libdarknet")
        logpipe = CTypesLogPipe(logger, logging.DEBUG, 1)
        self._network, self._labels = self._darknet.load_network(
            self._config[CONFIG_MODEL_CONFIG],
            self.darknet_data_path,
            self._config[CONFIG_MODEL_PATH],
            batch_size=1,
        )
        logpipe.close()
        self._process_initialization_done.set()

    def _detect(self, frame, min_confidence):
        """Run detection on frame."""
        self._darknet.copy_image_from_bytes(self._darknet_image, frame)
        detections = self._darknet.detect_image(
            self._network,
            self._labels,
            self._darknet_image,
            thresh=min_confidence,
        )
        return detections

    def work_input(self, item):
        """Perform object detection."""
        item["result"] = self._detect(item["frame"], item["min_confidence"])
        return item

    def work_output(self, item) -> None:
        """Put result into queue."""
        pop_if_full(self._result_queues[item["camera_identifier"]], item)

    def preprocess(self, frame) -> bytes:
        """Pre process frame before detection."""
        return letterbox_resize(frame, self.model_width, self.model_height).tobytes()

    def detect(
        self,
        frame: np.ndarray,
        camera_identifier: str,
        result_queue,
        min_confidence: float,
    ):
        """Perform detection."""
        self._result_queues[camera_identifier] = result_queue
        pop_if_full(
            self.input_queue,
            {
                "frame": frame,
                "camera_identifier": camera_identifier,
                "min_confidence": min_confidence,
            },
        )
        try:
            item = result_queue.get(timeout=3)
        except Empty:
            return None
        return item["result"]

    def post_process(self, detections, camera_resolution):
        """Post process detections."""
        _detections = []
        for label, confidence, box in detections:
            _detections.append(
                DetectedObject.from_absolute_letterboxed(
                    str(label),
                    confidence,
                    box[0],
                    box[1],
                    box[2],
                    box[3],
                    frame_res=camera_resolution,
                    model_res=self.model_res,
                )
            )

        return _detections

    @property
    def model_width(self) -> int:
        """Return trained model width."""
        return self._model_width

    @property
    def model_height(self) -> int:
        """Return trained model height."""
        return self._model_height

    @property
    def model_res(self):
        """Return trained model resolution."""
        return self.model_width, self.model_height

    @property
    def darknet_data_path(self) -> str:
        """Return path to Darknet data file."""
        homedir = os.path.expanduser(f"~{pwd.getpwuid(os.geteuid())[0]}")
        return f"{homedir}/darknet_data.data"
