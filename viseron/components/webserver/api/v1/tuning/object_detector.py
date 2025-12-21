"""Object detector tuning handler."""

import logging
from typing import Any

from .base import BaseTuningHandler

LOGGER = logging.getLogger(__name__)


class ObjectDetectorTuningHandler(BaseTuningHandler):
    """Handler for object detector configuration updates."""

    def update(self, camera_id: str, component: str, data: dict[str, Any]) -> bool:
        """Update object detector configuration."""
        camera_config = self._get_camera_config(camera_id, component, "object_detector")
        if camera_config is None:
            return False

        # Update labels with merge strategy
        if "labels" in data:
            existing_labels = camera_config.get("labels", [])
            merged_labels = self._merge_labels(existing_labels, data["labels"])
            if merged_labels:
                camera_config["labels"] = merged_labels
            elif "labels" in camera_config:
                del camera_config["labels"]

        # Update zones with merge strategy
        if "zones" in data:
            existing_zones = camera_config.get("zones", [])
            merged_zones = self._merge_zones(existing_zones, data["zones"])
            if merged_zones:
                camera_config["zones"] = merged_zones
            elif "zones" in camera_config:
                del camera_config["zones"]

        # Update mask (always replace)
        if "mask" in data:
            if data["mask"]:
                camera_config["mask"] = data["mask"]
            elif "mask" in camera_config:
                del camera_config["mask"]

        # Update all other fields (miscellaneous fields like fps, etc.)
        # Frontend should filter out internal fields before sending
        for key, value in data.items():
            if key not in {"labels", "zones", "mask"}:
                if value is not None:
                    # Preserve YAML tags if existing value has one
                    if key in camera_config:
                        existing_value = camera_config[key]
                        if (
                            hasattr(existing_value, "tag")
                            and existing_value.tag is not None
                            and str(existing_value.value) == str(value)
                        ):
                            # Keep the tagged value
                            continue
                    camera_config[key] = value
                elif key in camera_config:
                    # Remove key if value is None (allows deletion)
                    del camera_config[key]

        return True
