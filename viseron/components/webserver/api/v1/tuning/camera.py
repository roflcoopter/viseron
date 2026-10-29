"""Camera tuning handler."""

import logging
from typing import Any

from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN

from .base import BaseTuningHandler

LOGGER = logging.getLogger(__name__)


class CameraTuningHandler(BaseTuningHandler):
    """Handler for camera configuration updates."""

    def update(self, camera_id: str, component: str, data: dict[str, Any]) -> bool:
        """Update camera configuration."""
        camera_config = self._get_camera_config(camera_id, component, CAMERA_DOMAIN)
        if camera_config is None:
            return False

        # Get camera_domain dict to update it
        camera_domain = self.config[component][CAMERA_DOMAIN]

        updated_config = self._preserve_yaml_tags(camera_config, data)
        camera_domain[camera_id] = updated_config

        return True
