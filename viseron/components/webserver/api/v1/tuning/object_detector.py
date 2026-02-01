"""Object detector tuning handler."""

import logging
from typing import Any

from viseron.domains.object_detector.const import (
    CONFIG_LABELS,
    CONFIG_MASK,
    CONFIG_ZONES,
    DOMAIN as OBJECT_DETECTOR_DOMAIN,
)

from .base import BaseTuningHandler

LOGGER = logging.getLogger(__name__)


class ObjectDetectorTuningHandler(BaseTuningHandler):
    """Handler for object detector configuration updates."""

    def update(self, camera_id: str, component: str, data: dict[str, Any]) -> bool:
        """Update object detector configuration."""
        camera_config = self._get_camera_config(
            camera_id, component, OBJECT_DETECTOR_DOMAIN
        )
        if camera_config is None:
            return False

        # Update labels with merge strategy
        if CONFIG_LABELS in data:
            existing_labels = camera_config.get(CONFIG_LABELS, [])
            merged_labels = self._merge_labels(existing_labels, data[CONFIG_LABELS])
            if merged_labels:
                camera_config[CONFIG_LABELS] = merged_labels
            elif CONFIG_LABELS in camera_config:
                del camera_config[CONFIG_LABELS]

        # Update zones with merge strategy
        if CONFIG_ZONES in data:
            existing_zones = camera_config.get(CONFIG_ZONES, [])
            merged_zones = self._merge_zones(existing_zones, data[CONFIG_ZONES])
            if merged_zones:
                camera_config[CONFIG_ZONES] = merged_zones
            elif CONFIG_ZONES in camera_config:
                del camera_config[CONFIG_ZONES]

        # Update mask (always replace)
        if CONFIG_MASK in data:
            if data[CONFIG_MASK]:
                camera_config[CONFIG_MASK] = data[CONFIG_MASK]
            elif CONFIG_MASK in camera_config:
                del camera_config[CONFIG_MASK]

        # Update all other fields (miscellaneous fields like fps, etc.)
        # Frontend should filter out internal fields before sending
        for key, value in data.items():
            if key not in {CONFIG_LABELS, CONFIG_ZONES, CONFIG_MASK}:
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
