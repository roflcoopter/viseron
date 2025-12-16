"""Constants for the Hailo component."""
from typing import Final

COMPONENT = "hailo"

HAILO8_DEFAULT_URL = (
    "https://hailo-model-zoo.s3.eu-west-2.amazonaws.com/"
    "ModelZoo/Compiled/v2.16.0/hailo8l/yolov11m.hef"
)
HAILO8L_DEFAULT_URL = (
    "https://hailo-model-zoo.s3.eu-west-2.amazonaws.com/"
    "ModelZoo/Compiled/v2.16.0/hailo8l/yolov11m.hef"
)

# CONFIG_SCHEMA constants
CONFIG_OBJECT_DETECTOR = "object_detector"
CONFIG_MULTI_PROCESS_SERVICE = "multi_process_service"

DEFAULT_MULTI_PROCESS_SERVICE: Final = False

DESC_COMPONENT = "Hailo configuration."
DESC_OBJECT_DETECTOR = "Object detector domain config."
DESC_MULTI_PROCESS_SERVICE = "Allow multiple processes to share the Hailo device."

# OBJECT_DETECTOR_SCHEMA constants
CONFIG_MODEL_PATH = "model_path"
CONFIG_LABEL_PATH = "label_path"
CONFIG_MAX_DETECTIONS = "max_detections"

DEFAULT_MODEL_PATH: Final = None
DEFAULT_LABEL_PATH = "/detectors/models/darknet/coco.names"
DEFAULT_MAX_DETECTIONS = 50

DESC_MODEL_PATH = (
    "Path or URL to a Hailo-8 model in HEF format."
    " If a URL is provided, the model will be downloaded on startup."
    " If not provided, a default model from Hailo's model zoo will be used.<br>"
    "Downloaded models are cached and won't be re-downloaded."
)
DESC_LABEL_PATH = (
    "Path to file containing trained labels. If not provided, the COCO labels file from"
    " the <code>darknet</code> component will be used."
)
DESC_MAX_DETECTIONS = "Maximum number of detections to return."
