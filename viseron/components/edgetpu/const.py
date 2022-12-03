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
DEFAULT_DEVICE = None

DESC_COMPONENT = "EdgeTPU Configuration."
DESC_OBJECT_DETECTOR = "Object detector domain config."
DESC_MODEL_PATH = "Path to model."
DESC_LABEL_PATH = "Path to the file containing labels for the model."
DESC_DEVICE = (
    "Which EdgeTPU to use. "
    "Change this if you have multiple devices and want to use a specific one."
)

# Image classification config constants
CONFIG_IMAGE_CLASSIFICATION = "image_classification"
CONFIG_CROP_CORRECTION = "crop_correction"

DESC_IMAGE_CLASSIFICATION = "Image classification domain config."
DESC_CROP_CORRECTION = (
    "Pad with this many pixels around the detected object.</br>"
    "The image sent to the classifier is cropped to the bounding box of the detected "
    "object. Without crop correction the accuracy of the classifier is reduced since "
    "most models are trained on images where the subject is centered in the image with "
    "some background around it."
)

DEFAULT_CROP_CORRECTION = 150


# Common config constants
DEFAULT_LABEL_PATH_MAP = {
    CONFIG_OBJECT_DETECTOR: DEFAULT_DETECTOR_LABEL_PATH,
    CONFIG_IMAGE_CLASSIFICATION: DEFAULT_CLASSIFIER_LABEL_PATH,
}
