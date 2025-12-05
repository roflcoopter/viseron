"""Label definitions for object detectors."""

import logging
import os

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


def load_labels_from_file(file_path: str) -> list[str]:
    """Load labels from file."""
    try:
        if not os.path.exists(file_path):
            return []
        with open(file_path, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except OSError as e:
        LOGGER.warning(f"Failed to load labels from {file_path}: {e}")
        return []


def get_available_labels(component_name: str, cam_config: dict) -> list[str] | None:
    """Get available labels for an object detector component."""
    if component_name == "darknet":
        return load_labels_from_file("/detectors/models/darknet/coco.names")
    if component_name == "hailo":
        return load_labels_from_file("/detectors/models/darknet/coco.names")
    if component_name == "edgetpu":
        return load_labels_from_file("/detectors/models/edgetpu/labels.txt")
    if component_name == "deepstack":
        return load_labels_from_file("/detectors/models/darknet/coco.names")
    if component_name == "codeprojectai":
        # Get custom_model from config, default to ipcam-general
        custom_model = cam_config.get("custom_model", "ipcam-general")
        if custom_model is None:
            custom_model = "ipcam-general"
        return CODEPROJECTAI_MODELS.get(custom_model, [])
    return None
