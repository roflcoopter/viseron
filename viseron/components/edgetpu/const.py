"""EdgeTPU constants."""
COMPONENT = "edgetpu"


DEVICE_CPU = "cpu"
DEFAULT_DETECTOR_CPU_MODEL = (
    "/detectors/models/edgetpu/efficientdet_lite3_cpu_model.tflite"
)
DEFAULT_DETECTOR_EDGETPU_MODEL = "/detectors/models/edgetpu/mobiledet_model.tflite"
DEFAULT_DETECTOR_LABEL_PATH = "/detectors/models/edgetpu/labels.txt"

DEFAULT_CLASSIFIER_CPU_MODEL = (
    "/classifiers/models/edgetpu/tf2_mobilenet_v3_edgetpu_1.0_224_ptq_cpu.tflite"
)
DEFAULT_CLASSIFIER_EDGETPU_MODEL = (
    "/classifiers/models/edgetpu/tf2_mobilenet_v3_edgetpu_1.0_224_ptq_edgetpu.tflite"
)
DEFAULT_CLASSIFIER_LABEL_PATH = "/classifiers/models/edgetpu/labels.txt"


# Object detector config constants
CONFIG_OBJECT_DETECTOR = "object_detector"
CONFIG_MODEL_PATH = "model_path"
CONFIG_LABEL_PATH = "label_path"
CONFIG_DEVICE = "device"

DEFAULT_NAME = "edgetpu"
DEFAULT_MODEL_PATH = None
DEFAULT_LABEL_PATH = None
DEFAULT_DEVICE = None


# Image classification config constants
CONFIG_IMAGE_CLASSIFICATION = "image_classification"


DEFAULT_LABEL_PATH_MAP = {
    CONFIG_OBJECT_DETECTOR: DEFAULT_DETECTOR_LABEL_PATH,
    CONFIG_IMAGE_CLASSIFICATION: DEFAULT_CLASSIFIER_LABEL_PATH,
}
