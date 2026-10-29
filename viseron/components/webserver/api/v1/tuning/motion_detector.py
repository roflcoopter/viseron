"""Motion detector tuning handler."""

import logging
from typing import Any

from viseron.domains.motion_detector.const import (
    CONFIG_MASK,
    DOMAIN as MOTION_DETECTOR_DOMAIN,
)

from .base import BaseTuningHandler

LOGGER = logging.getLogger(__name__)


class MotionDetectorTuningHandler(BaseTuningHandler):
    """Handler for motion detector configuration updates."""

    def update(self, camera_id: str, component: str, data: dict[str, Any]) -> bool:
        """Update motion detector configuration."""
        camera_config = self._get_camera_config(
            camera_id, component, MOTION_DETECTOR_DOMAIN
        )
        if camera_config is None:
            return False

        # Update mask (always replace)
        if CONFIG_MASK in data:
            if data[CONFIG_MASK]:
                camera_config[CONFIG_MASK] = data[CONFIG_MASK]
            elif CONFIG_MASK in camera_config:
                del camera_config[CONFIG_MASK]

        # Update all other fields (miscellaneous fields)
        # Frontend should filter out internal fields before sending
        for key, value in data.items():
            if key != CONFIG_MASK:
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
