"""EdgeTPU constants."""
COMPONENT = "edgetpu"

CONFIG_OBJECT_DETECTOR = "object_detector"
CONFIG_MODEL_PATH = "model_path"
CONFIG_LABEL_PATH = "label_path"
CONFIG_DEVICE = "device"
CONFIG_CAMERAS = "cameras"

DEFAULT_NAME = "edgetpu"
DEFAULT_MODEL_PATH = "/detectors/models/edgetpu/model.tflite"
DEFAULT_LABEL_PATH = "/detectors/models/edgetpu/labels.txt"
DEFAULT_DEVICE = ":0"
