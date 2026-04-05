"""Label definitions for object detectors."""

import logging
import os

from ultralytics import YOLO

from viseron.components.codeprojectai.const import (
    COMPONENT as CODEPROJECTAI_COMPONENT,
    CONFIG_CUSTOM_MODEL as CODEPROJECTAI_CONFIG_CUSTOM_MODEL,
    DEFAULT_CUSTOM_MODEL as CODEPROJECTAI_DEFAULT_CUSTOM_MODEL,
)
from viseron.components.darknet.const import (
    COMPONENT as DARKNET_COMPONENT,
    CONFIG_LABEL_PATH as DARKNET_CONFIG_LABEL_PATH,
    DEFAULT_LABEL_PATH as DARKNET_LABEL_PATH,
)
from viseron.components.deepstack.const import (
    COMPONENT as DEEPSTACK_COMPONENT,
    CONFIG_CUSTOM_MODEL as DEEPSTACK_CONFIG_CUSTOM_MODEL,
)
from viseron.components.edgetpu.const import (
    COMPONENT as EDGETPU_COMPONENT,
    CONFIG_LABEL_PATH as EDGETPU_CONFIG_LABEL_PATH,
    DEFAULT_CLASSIFIER_LABEL_PATH,
)
from viseron.components.hailo.const import (
    COMPONENT as HAILO_COMPONENT,
    CONFIG_LABEL_PATH as HAILO_CONFIG_LABEL_PATH,
    DEFAULT_LABEL_PATH as HAILO_LABEL_PATH,
)
from viseron.components.yolo.const import (
    COMPONENT as YOLO_COMPONENT,
    CONFIG_MODEL_PATH as YOLO_CONFIG_MODEL_PATH,
)

LOGGER = logging.getLogger(__name__)

CODEPROJECTAI_MODELS = {
    "ipcam-animal": [
        "bird",
        "cat",
        "dog",
        "horse",
        "sheep",
        "cow",
        "bear",
        "deer",
        "rabbit",
        "raccoon",
        "fox",
        "skunk",
        "squirrel",
        "pig",
    ],
    "ipcam-dark": ["bicycle", "bus", "car", "cat", "dog", "motorcycle", "person"],
    "ipcam-general": [
        "person",
        "vehicle",
        # ipcam-dark :
        "bicycle",
        "bus",
        "car",
        "cat",
        "dog",
        "motorcycle",
    ],
    "ipcam-combined": [
        "person",
        "bicycle",
        "car",
        "motorcycle",
        "bus",
        "truck",
        "bird",
        "cat",
        "dog",
        "horse",
        "sheep",
        "cow",
        "bear",
        "deer",
        "rabbit",
        "raccoon",
        "fox",
        "skunk",
        "squirrel",
        "pig",
    ],
}


def _load_labels_from_file(file_path: str) -> list[str]:
    """Load labels from file."""
    try:
        if not os.path.exists(file_path):
            return []
        with open(file_path, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except OSError as e:
        LOGGER.warning(f"Failed to load labels from {file_path}: {e}")
        return []


def _load_yolo_labels(model_path: str) -> list[str] | None:
    """Load labels from YOLO model."""
    try:
        if not os.path.exists(model_path):
            LOGGER.warning(f"YOLO model not found: {model_path}")
            return None

        model = YOLO(model_path)
        return list(model.names.values())
    except (OSError, RuntimeError) as e:
        LOGGER.warning(f"Failed to load YOLO labels from {model_path}: {e}")
        return None


def get_available_labels(
    component_name: str, domain_config: dict | None = None
) -> list[str] | None:
    """Get available labels for an object detector component."""
    if component_name == DARKNET_COMPONENT:
        label_path = DARKNET_LABEL_PATH
        if domain_config and DARKNET_CONFIG_LABEL_PATH in domain_config:
            label_path = domain_config[DARKNET_CONFIG_LABEL_PATH]
        return _load_labels_from_file(label_path)

    if component_name == HAILO_COMPONENT:
        label_path = HAILO_LABEL_PATH
        if domain_config and HAILO_CONFIG_LABEL_PATH in domain_config:
            label_path = domain_config[HAILO_CONFIG_LABEL_PATH]
        return _load_labels_from_file(label_path)

    if component_name == EDGETPU_COMPONENT:
        label_path = DEFAULT_CLASSIFIER_LABEL_PATH
        if domain_config and EDGETPU_CONFIG_LABEL_PATH in domain_config:
            label_path = domain_config[EDGETPU_CONFIG_LABEL_PATH]
        return _load_labels_from_file(label_path)

    if component_name == DEEPSTACK_COMPONENT:
        if domain_config and domain_config.get(DEEPSTACK_CONFIG_CUSTOM_MODEL):
            return None  # No available labels for custom models
        return _load_labels_from_file(DARKNET_LABEL_PATH)  # Default options

    if component_name == CODEPROJECTAI_COMPONENT:
        selected_model = CODEPROJECTAI_DEFAULT_CUSTOM_MODEL  # Default model
        if domain_config and CODEPROJECTAI_CONFIG_CUSTOM_MODEL in domain_config:
            selected_model = domain_config[CODEPROJECTAI_CONFIG_CUSTOM_MODEL]
        return CODEPROJECTAI_MODELS.get(selected_model, [])

    if component_name == YOLO_COMPONENT:
        # YOLO requires model_path to be configured (no default model)
        if not domain_config or YOLO_CONFIG_MODEL_PATH not in domain_config:
            return None
        return _load_yolo_labels(domain_config[YOLO_CONFIG_MODEL_PATH])

    return None
