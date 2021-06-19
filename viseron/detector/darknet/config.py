"""Darknet config."""
import os
from typing import Union

from cv2.dnn import (
    DNN_BACKEND_CUDA,
    DNN_BACKEND_DEFAULT,
    DNN_BACKEND_OPENCV,
    DNN_TARGET_CPU,
    DNN_TARGET_CUDA,
    DNN_TARGET_OPENCL,
)
from voluptuous import All, Any, Coerce, Maybe, Optional, Range

from viseron.const import ENV_CUDA_SUPPORTED, ENV_OPENCL_SUPPORTED
from viseron.detector import AbstractDetectorConfig

from .defaults import LABEL_PATH, MODEL_CONFIG, MODEL_PATH

SCHEMA = AbstractDetectorConfig.SCHEMA.extend(
    {
        Optional("model_path", default=MODEL_PATH): str,
        Optional("model_config", default=MODEL_CONFIG): str,
        Optional("model_width", default=None): Maybe(int),
        Optional("model_height", default=None): Maybe(int),
        Optional("label_path", default=LABEL_PATH): str,
        Optional("suppression", default=0.4): All(
            Any(0, 1, All(float, Range(min=0.0, max=1.0))), Coerce(float)
        ),
    }
)


class Config(AbstractDetectorConfig):
    """Darknet object detection config."""

    def __init__(self, detector_config):
        super().__init__(detector_config)
        self._model_path = detector_config["model_path"]
        self._model_config = detector_config["model_config"]
        self._model_width = detector_config["model_width"]
        self._model_height = detector_config["model_height"]
        self._label_path = detector_config["label_path"]
        self._suppression = detector_config["suppression"]

    @property
    def model_path(self):
        """Return path to object detection model."""
        return self._model_path

    @property
    def model_config(self):
        """Return model config path."""
        return self._model_config

    @property
    def model_width(self) -> Union[int, None]:
        """Return width that images will be resized to before running detection."""
        return self._model_width

    @property
    def model_height(self) -> Union[int, None]:
        """Return height that images will be resized to before running detection."""
        return self._model_height

    @property
    def label_path(self):
        """Return path to object detection labels."""
        return self._label_path

    @property
    def suppression(self):
        """Return threshold for non maximum suppression."""
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
