"""Camera tuning handler."""

import logging
from typing import Any

from .base import BaseTuningHandler

LOGGER = logging.getLogger(__name__)


class CameraTuningHandler(BaseTuningHandler):
    """Handler for camera configuration updates."""

    def update(self, camera_id: str, component: str, data: dict[str, Any]) -> bool:
        """Update camera configuration."""
        camera_config = self._get_camera_config(camera_id, component, "camera")
        if camera_config is None:
            return False

        # Get camera_domain dict to update it
        camera_domain = self.config[component]["camera"]

        # Replace camera configuration entirely with data from request
        # Frontend should filter out internal fields before sending
        camera_domain[camera_id] = data

        return True
