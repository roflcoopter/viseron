"""License plate recognition tuning handler."""

import logging
from typing import Any

from .base import BaseTuningHandler

LOGGER = logging.getLogger(__name__)


class LicensePlateRecognitionTuningHandler(BaseTuningHandler):
    """Handler for license plate recognition configuration updates."""

    def update(self, camera_id: str, component: str, data: dict[str, Any]) -> bool:
        """Update license plate recognition configuration."""
        camera_config = self._get_camera_config(
            camera_id, component, "license_plate_recognition"
        )
        if camera_config is None:
            return False

        # Get cameras dict to update it later
        cameras = self.config[component]["license_plate_recognition"]["cameras"]

        # Build ordered config with labels first, then mask, then other fields
        ordered_config = {}

        # Update labels (simple list of strings for license_plate_recognition)
        if "labels" in data:
            if data["labels"]:
                ordered_config["labels"] = data["labels"]
            # If labels is empty/None, don't include it (will be deleted from existing)
        elif "labels" in camera_config:
            # Preserve existing labels if not in data
            ordered_config["labels"] = camera_config["labels"]

        # Update mask (always replace)
        if "mask" in data:
            if data["mask"]:
                ordered_config["mask"] = data["mask"]
            # If mask is empty/None, don't include it (will be deleted from existing)
        elif "mask" in camera_config:
            # Preserve existing mask if not in data
            ordered_config["mask"] = camera_config["mask"]

        # Update all other fields (miscellaneous fields)
        # Frontend should filter out internal fields before sending
        for key, value in camera_config.items():
            if key not in {"labels", "mask"}:
                ordered_config[key] = value

        for key, value in data.items():
            if key not in {"labels", "mask"}:
                if value is not None:
                    ordered_config[key] = value

        # Replace camera_config with ordered version
        cameras[camera_id] = ordered_config

        return True
