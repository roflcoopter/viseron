"""Darknet constants."""
from __future__ import annotations

from typing import Final

import cv2

COMPONENT: Final = "darknet"


# CONFIG_SCHEMA constants
CONFIG_OBJECT_DETECTOR: Final = "object_detector"
CONFIG_MODEL_PATH: Final = "model_path"
CONFIG_MODEL_CONFIG: Final = "model_config"
CONFIG_LABEL_PATH: Final = "label_path"
CONFIG_SUPPRESSION: Final = "suppression"
CONFIG_DNN_BACKEND: Final = "dnn_backend"
CONFIG_DNN_TARGET: Final = "dnn_target"
CONFIG_HALF_PRECISION: Final = "half_precision"

DEFAULT_MODEL_PATH: Final = "/detectors/models/darknet/default.weights"
DEFAULT_MODEL_CONFIG: Final = "/detectors/models/darknet/default.cfg"
DEFAULT_LABEL_PATH: Final = "/detectors/models/darknet/coco.names"
DEFAULT_SUPPRESSION: Final = 0.4
DEFAULT_DNN_BACKEND: Final = None
DEFAULT_DNN_TARGET: Final = None
DEFAULT_HALF_PRECISION: Final = False

DESC_COMPONENT = "Darknet configuration."
DESC_OBJECT_DETECTOR = "Object detector domain config."
DESC_MODEL_PATH = "Path to model (YOLO *.weights file)"
DESC_MODEL_CONFIG = "Path to config (YOLO *.cfg file)"
DESC_LABEL_PATH = "Path to file containing trained labels."
DESC_SUPPRESSION = (
    "Non-maxima suppression, "
    "used to remove overlapping detections.<br>"
    "You can read more about how this works "
    "<a href=https://towardsdatascience.com/non-maximum-suppression-nms-93ce178e177c>"
    "here.</a>"
)
DESC_DNN_BACKEND = "OpenCV DNN Backend."
DESC_DNN_TARGET = "OpenCV DNN Target."
DESC_HALF_PRECISION = (
    "Enable/disable half precision accuracy.<br>"
    "If your GPU supports FP16, enabling this might give you a performance increase."
)


# DNN backend/target constants
DNN_DEFAULT = "default"
DNN_CPU = "cpu"
DNN_OPENCV = "opencv"
DNN_OPENCL = "opencl"
DNN_OPENCL_FP16 = "opencl_fp16"
DNN_OPENVINO = "openvino"

DNN_BACKENDS: dict[str, int] = {
    DNN_DEFAULT: cv2.dnn.DNN_BACKEND_DEFAULT,
    DNN_OPENCV: cv2.dnn.DNN_BACKEND_OPENCV,
    DNN_OPENVINO: cv2.dnn.DNN_BACKEND_INFERENCE_ENGINE,
}
DNN_TARGETS: dict[str, int] = {
    DNN_CPU: cv2.dnn.DNN_TARGET_CPU,
    DNN_OPENCL: cv2.dnn.DNN_TARGET_OPENCL,
    DNN_OPENCL_FP16: cv2.dnn.DNN_TARGET_OPENCL_FP16,
}
