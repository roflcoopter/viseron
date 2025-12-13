"""Constants for the YOLO component."""
from typing import Final

COMPONENT = "yolo"

# CONFIG_SCHEMA constants
CONFIG_OBJECT_DETECTOR = "object_detector"

# OBJECT_DETECTOR_SCHEMA constants
CONFIG_MODEL_PATH = "model_path"
CONFIG_MIN_CONFIDENCE = "min_confidence"
CONFIG_IOU = "iou"
CONFIG_HALF_PRECISION = "half_precision"
CONFIG_DEVICE = "device"

DEFAULT_MODEL_PATH: Final = None
DEFAULT_MIN_CONFIDENCE = 0.25
DEFAULT_IOU = 0.7
DEFAULT_HALF_PRECISION = False
DEFAULT_DEVICE: Final = None

DESC_COMPONENT = "YOLO configuration."
DESC_OBJECT_DETECTOR = "Object detector domain config."

DESC_MODEL_PATH = "Path to a YOLO model. See <i>Pre-trained models</i> below."
DESC_MIN_CONFIDENCE = (
    "Minimum confidence to consider a detection.<br>"
    "This minimum is enforced during inference before being filtered by values "
    "in <code>labels</code>"
)
DESC_IOU = "Intersection Over Union (IoU) threshold for Non-Maximum Suppression (NMS)."
DESC_HALF_PRECISION = (
    "Enable/disable half precision accuracy.<br>"
    "If your GPU supports FP16, enabling this might give you a performance increase."
)
DESC_DEVICE = "Specifies the device for inference (e.g., cpu, cuda:0 or 0)."
