"""fast-alpr constants."""

from typing import Final

COMPONENT: Final = "fastalpr"

DESC_COMPONENT: Final = "fast-alpr configuration."

# CONFIG_SCHEMA constants
CONFIG_LICENSE_PLATE_RECOGNITION: Final = "license_plate_recognition"

DESC_LICENSE_PLATE_RECOGNITION: Final = "License plate recognition domain config."

# LICENSE_PLATE_RECOGNITION_SCHEMA constants
CONFIG_DETECTOR_MODEL: Final = "detector_model"
CONFIG_DETECTOR_CONF_THRESH: Final = "detector_confidence"
CONFIG_OCR_MODEL: Final = "ocr_model"
CONFIG_DEVICE: Final = "device"
CONFIG_DISCARD_UNRECOGNIZED_PLATES: Final = "discard_unrecognized_plates"

DEFAULT_DETECTOR_MODEL: Final = "yolo-v9-t-384-license-plate-end2end"
DEFAULT_DETECTOR_CONF_THRESH: Final = 0.4
DEFAULT_OCR_MODEL: Final = "cct-xs-v2-global-model"
DEFAULT_DEVICE: Final = "auto"
DEFAULT_DISCARD_UNRECOGNIZED_PLATES: Final = True

DESC_DETECTOR_MODEL: Final = (
    "Which license plate detector model to use. "
    "See <a href=#models>models</a> for more information on this."
)
DESC_DETECTOR_CONF_THRESH: Final = (
    "Minimum confidence for the detector to consider something a license plate. "
    "This is separate from <code>min_confidence</code>, which instead filters the "
    "result of the OCR reading."
)
DESC_OCR_MODEL: Final = (
    "Which OCR model to use to read the characters of a detected license plate. "
    "See <a href=#models>models</a> for more information on this."
)
DESC_DEVICE: Final = (
    "Device used to run inference on.<br>"
    "<code>auto</code> lets ONNX Runtime pick the best available provider. "
    "<code>cuda</code> requires an NVIDIA GPU with CUDA/cuDNN available, and is "
    "only bundled in the <code>amd64-cuda</code> image. On all other images the "
    "CUDA provider is unavailable and inference falls back to the CPU."
)
DESC_DISCARD_UNRECOGNIZED_PLATES: Final = (
    "The OCR model can detect a license plate-shaped region but fail to read any "
    "characters from it, returning an empty plate text. This can happen even when "
    "<code>min_confidence</code> is set high, since the model's confidence in "
    "this case does not reflect whether any characters were actually read. "
    "If <code>true</code>, these empty results are discarded instead of being "
    "reported as a detection."
)

SUPPORTED_DETECTOR_MODELS: Final = [
    "yolo-v9-s-608-license-plate-end2end",
    "yolo-v9-t-640-license-plate-end2end",
    "yolo-v9-t-512-license-plate-end2end",
    "yolo-v9-t-416-license-plate-end2end",
    "yolo-v9-t-384-license-plate-end2end",
    "yolo-v9-t-256-license-plate-end2end",
]

SUPPORTED_OCR_MODELS: Final = [
    "cct-s-v2-global-model",
    "cct-xs-v2-global-model",
    "cct-s-v1-global-model",
    "cct-xs-v1-global-model",
    "cct-s-relu-v1-global-model",
    "cct-xs-relu-v1-global-model",
    "argentinian-plates-cnn-model",
    "argentinian-plates-cnn-synth-model",
    "european-plates-mobile-vit-v2-model",
    "global-plates-mobile-vit-v2-model",
]

SUPPORTED_DEVICES: Final = [
    "auto",
    "cpu",
    "cuda",
]

# Viseron data keys
LOCK: Final = "lock"
INSTANCES: Final = "instances"
