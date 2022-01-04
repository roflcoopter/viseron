"""Darknet object detection."""
import configparser
import logging
import os

import cv2
import voluptuous as vol

from viseron import Viseron
from viseron.const import ENV_CUDA_SUPPORTED, ENV_OPENCL_SUPPORTED
from viseron.domains import setup_domain
from viseron.domains.object_detector import BASE_CONFIG_SCHEMA
from viseron.helpers.subprocess import POPEN_LOCK

from .const import (
    COMPONENT,
    CONFIG_DNN_BACKEND,
    CONFIG_DNN_TARGET,
    CONFIG_LABEL_PATH,
    CONFIG_MODEL_CONFIG,
    CONFIG_MODEL_HEIGHT,
    CONFIG_MODEL_PATH,
    CONFIG_MODEL_WIDTH,
    CONFIG_OBJECT_DETECTOR,
    CONFIG_SUPPRESSION,
    DEFAULT_DNN_BACKEND,
    DEFAULT_DNN_TARGET,
    DEFAULT_LABEL_PATH,
    DEFAULT_MODEL_CONFIG,
    DEFAULT_MODEL_HEIGHT,
    DEFAULT_MODEL_PATH,
    DEFAULT_MODEL_WIDTH,
    DEFAULT_SUPPRESSION,
    DNN_BACKENDS,
    DNN_CPU,
    DNN_CUDA,
    DNN_DEFAULT,
    DNN_OPENCL,
    DNN_TARGETS,
)

LOGGER = logging.getLogger(__name__)

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
                            CONFIG_MODEL_CONFIG, default=DEFAULT_MODEL_CONFIG
                        ): str,
                        vol.Optional(
                            CONFIG_MODEL_WIDTH, default=DEFAULT_MODEL_WIDTH
                        ): vol.Maybe(int),
                        vol.Optional(
                            CONFIG_MODEL_HEIGHT, default=DEFAULT_MODEL_HEIGHT
                        ): vol.Maybe(int),
                        vol.Optional(
                            CONFIG_LABEL_PATH, default=DEFAULT_LABEL_PATH
                        ): str,
                        vol.Optional(
                            CONFIG_SUPPRESSION, default=DEFAULT_SUPPRESSION
                        ): vol.Any(
                            0,
                            1,
                            vol.All(float, vol.Range(min=0.0, max=1.0)),
                            vol.Coerce(float),
                        ),
                        vol.Optional(
                            CONFIG_DNN_BACKEND, default=DEFAULT_DNN_BACKEND
                        ): vol.Any(vol.In(DNN_BACKENDS), None),
                        vol.Optional(
                            CONFIG_DNN_TARGET, default=DEFAULT_DNN_TARGET
                        ): vol.Any(vol.In(DNN_TARGETS), None),
                    }
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config):
    """Set up the darknet component."""
    config = config[COMPONENT]
    vis.data[COMPONENT] = Darknet(vis, config[CONFIG_OBJECT_DETECTOR])
    for domain in config.keys():
        setup_domain(vis, COMPONENT, domain, config)

    return True


class Darknet:
    """Darknet object detector interface."""

    def __init__(self, vis, config):
        self._vis = vis
        self._config = config
        # Activate OpenCL
        if cv2.ocl.haveOpenCL():
            LOGGER.debug("Enabling OpenCL")
            cv2.ocl.setUseOpenCL(True)

        self.load_labels(config[CONFIG_LABEL_PATH])
        self.load_network(
            config[CONFIG_MODEL_PATH],
            config[CONFIG_MODEL_CONFIG],
            self.dnn_preferable_backend,
            self.dnn_preferable_target,
        )

        LOGGER.debug(
            f"Using weights {config[CONFIG_MODEL_PATH]} and "
            f"config {config[CONFIG_MODEL_CONFIG]}"
        )

        model_config = configparser.ConfigParser(strict=False)
        model_config.read(config[CONFIG_MODEL_CONFIG])
        self._model_width = (
            config[CONFIG_MODEL_WIDTH]
            if config[CONFIG_MODEL_WIDTH]
            else int(model_config.get("net", "width"))
        )
        self._model_height = (
            config[CONFIG_MODEL_HEIGHT]
            if config[CONFIG_MODEL_HEIGHT]
            else int(model_config.get("net", "height"))
        )

        self._model = cv2.dnn_DetectionModel(self._net)
        self._model.setInputParams(
            size=(self.model_width, self.model_height), scale=1 / 255
        )

        self._nms = config[CONFIG_SUPPRESSION]
        self._result_queues = {}

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
        self._net = cv2.dnn.readNet(  # pylint:disable=no-member
            model, model_config, "darknet"
        )
        self._net.setPreferableBackend(backend)
        self._net.setPreferableTarget(target)

    def detect(self, frame, min_confidence):
        """Run detection on frame."""
        # This lock must be used because OpenCVs DNN bugs out when spawning subprocesses
        # See https://github.com/opencv/opencv/issues/19643
        with POPEN_LOCK:
            return self._model.detect(
                frame,
                min_confidence,
                self._nms,
            )

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
    def dnn_preferable_backend(self):
        """Return DNN backend."""
        if self._config[CONFIG_DNN_BACKEND]:
            return self._config[CONFIG_DNN_BACKEND]
        if os.getenv(ENV_CUDA_SUPPORTED) == "true":
            return DNN_BACKENDS[DNN_CUDA]
        if os.getenv(ENV_OPENCL_SUPPORTED) == "true":
            return DNN_BACKENDS[DNN_OPENCL]
        return DNN_BACKENDS[DNN_DEFAULT]

    @property
    def dnn_preferable_target(self):
        """Return DNN target."""
        if self._config[CONFIG_DNN_TARGET]:
            return self._config[CONFIG_DNN_TARGET]
        if os.getenv(ENV_CUDA_SUPPORTED) == "true":
            return DNN_TARGETS[DNN_CUDA]
        if os.getenv(ENV_OPENCL_SUPPORTED) == "true":
            return DNN_TARGETS[DNN_OPENCL]
        return DNN_TARGETS[DNN_CPU]
