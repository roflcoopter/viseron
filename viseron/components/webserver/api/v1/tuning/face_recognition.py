"""Face recognition tuning handler."""

import logging
from typing import Any

from viseron.domains.face_recognition.const import DOMAIN as FACE_RECOGNITION_DOMAIN
from viseron.domains.post_processor.const import (
    CONFIG_CAMERAS,
    CONFIG_LABELS,
    CONFIG_MASK,
)

from .base import BaseTuningHandler

LOGGER = logging.getLogger(__name__)


class FaceRecognitionTuningHandler(BaseTuningHandler):
    """Handler for face recognition configuration updates."""

    def update(self, camera_id: str, component: str, data: dict[str, Any]) -> bool:
        """Update face recognition configuration."""
        camera_config = self._get_camera_config(
            camera_id, component, FACE_RECOGNITION_DOMAIN
        )
        if camera_config is None:
            return False

        # Get cameras dict to update it later
        cameras = self.config[component][FACE_RECOGNITION_DOMAIN][CONFIG_CAMERAS]

        # Build ordered config with labels first, then mask, then other fields
        ordered_config = {}

        # Update labels (simple list of strings for face_recognition)
        if CONFIG_LABELS in data:
            if data[CONFIG_LABELS]:
                ordered_config[CONFIG_LABELS] = data[CONFIG_LABELS]
            # If labels is empty/None, don't include it (will be deleted from existing)
        elif CONFIG_LABELS in camera_config:
            # Preserve existing labels if not in data
            ordered_config[CONFIG_LABELS] = camera_config[CONFIG_LABELS]

        # Update mask (always replace)
        if CONFIG_MASK in data:
            if data[CONFIG_MASK]:
                ordered_config[CONFIG_MASK] = data[CONFIG_MASK]
            # If mask is empty/None, don't include it (will be deleted from existing)
        elif CONFIG_MASK in camera_config:
            # Preserve existing mask if not in data
            ordered_config[CONFIG_MASK] = camera_config[CONFIG_MASK]

        # Update all other fields (miscellaneous fields like expire_after, etc.)
        # Frontend should filter out internal fields before sending
        for key, value in camera_config.items():
            if key not in {CONFIG_LABELS, CONFIG_MASK}:
                ordered_config[key] = value

        for key, value in data.items():
            if key not in {CONFIG_LABELS, CONFIG_MASK}:
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
                            ordered_config[key] = existing_value
                            continue
                    ordered_config[key] = value

        # Replace camera_config with ordered version
        cameras[camera_id] = ordered_config

        return True
