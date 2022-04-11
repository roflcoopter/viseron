"""Darknet constants."""
from cv2.dnn import (
    DNN_BACKEND_DEFAULT,
    DNN_BACKEND_OPENCV,
    DNN_TARGET_CPU,
    DNN_TARGET_OPENCL,
    DNN_TARGET_OPENCL_FP16,
)

COMPONENT = "darknet"


# CONFIG_SCHEMA constants
CONFIG_OBJECT_DETECTOR = "object_detector"
CONFIG_MODEL_PATH = "model_path"
CONFIG_MODEL_CONFIG = "model_config"
CONFIG_LABEL_PATH = "label_path"
CONFIG_SUPPRESSION = "suppression"
CONFIG_DNN_BACKEND = "dnn_backend"
CONFIG_DNN_TARGET = "dnn_target"
CONFIG_HALF_PRECISION = "half_precision"

DEFAULT_MODEL_PATH = "/detectors/models/darknet/default.weights"
DEFAULT_MODEL_CONFIG = "/detectors/models/darknet/default.cfg"
DEFAULT_LABEL_PATH = "/detectors/models/darknet/coco.names"
DEFAULT_SUPPRESSION = 0.4
DEFAULT_DNN_BACKEND = None
DEFAULT_DNN_TARGET = None
DEFAULT_HALF_PRECISION = False

# DNN backend/target constants
DNN_DEFAULT = "default"
DNN_CPU = "cpu"
DNN_OPENCV = "opencv"
DNN_OPENCL = "opencl"
DNN_OPENCL_FP16 = "opencl_fp16"

DNN_BACKENDS = {
    DNN_DEFAULT: DNN_BACKEND_DEFAULT,
    DNN_OPENCV: DNN_BACKEND_OPENCV,
}
DNN_TARGETS = {
    DNN_CPU: DNN_TARGET_CPU,
    DNN_OPENCL: DNN_TARGET_OPENCL,
    DNN_OPENCL_FP16: DNN_TARGET_OPENCL_FP16,
}
