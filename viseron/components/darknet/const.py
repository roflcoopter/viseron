"""Darknet constants."""
import cv2

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

DNN_BACKENDS = {
    DNN_DEFAULT: cv2.DNN_BACKEND_DEFAULT,
    DNN_OPENCV: cv2.DNN_BACKEND_OPENCV,
}
DNN_TARGETS = {
    DNN_CPU: cv2.DNN_TARGET_CPU,
    DNN_OPENCL: cv2.DNN_TARGET_OPENCL,
    DNN_OPENCL_FP16: cv2.DNN_TARGET_OPENCL_FP16,
}
