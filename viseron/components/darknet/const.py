"""Darknet constants."""
from cv2.dnn import (
    DNN_BACKEND_CUDA,
    DNN_BACKEND_DEFAULT,
    DNN_BACKEND_OPENCV,
    DNN_TARGET_CPU,
    DNN_TARGET_CUDA,
    DNN_TARGET_OPENCL,
)

COMPONENT = "darknet"


# CONFIG_SCHEMA constants
CONFIG_OBJECT_DETECTOR = "object_detector"
CONFIG_MODEL_PATH = "model_path"
CONFIG_MODEL_CONFIG = "model_config"
CONFIG_MODEL_WIDTH = "model_width"
CONFIG_MODEL_HEIGHT = "model_height"
CONFIG_LABEL_PATH = "label_path"
CONFIG_SUPPRESSION = "suppression"
CONFIG_DNN_BACKEND = "dnn_backend"
CONFIG_DNN_TARGET = "dnn_target"

DEFAULT_MODEL_PATH = "/detectors/models/darknet/default.weights"
DEFAULT_MODEL_CONFIG = "/detectors/models/darknet/default.cfg"
DEFAULT_MODEL_WIDTH = None
DEFAULT_MODEL_HEIGHT = None
DEFAULT_LABEL_PATH = "/detectors/models/darknet/coco.names"
DEFAULT_SUPPRESSION = 0.4
DEFAULT_DNN_BACKEND = None
DEFAULT_DNN_TARGET = None

# DNN backend/target constants
DNN_DEFAULT = "default"
DNN_CPU = "cpu"
DNN_CUDA = "cuda"
DNN_OPENCL = "opencv"

DNN_BACKENDS = {
    DNN_DEFAULT: DNN_BACKEND_DEFAULT,
    DNN_CUDA: DNN_BACKEND_CUDA,
    DNN_OPENCL: DNN_BACKEND_OPENCV,
}
DNN_TARGETS = {
    DNN_CPU: DNN_TARGET_CPU,
    DNN_CUDA: DNN_TARGET_CUDA,
    DNN_OPENCL: DNN_TARGET_OPENCL,
}
