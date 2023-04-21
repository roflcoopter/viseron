"""Cameras API Handler."""
from __future__ import annotations

import logging

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.const import DOMAIN_FAILED, REGISTERED_DOMAINS
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN

LOGGER = logging.getLogger(__name__)


class CamerasAPIHandler(BaseAPIHandler):
    """Handler for API calls related to cameras."""

    routes = [
        {
            "path_pattern": r"/cameras",
            "supported_methods": ["GET"],
            "method": "get_cameras",
        },
        {
            "path_pattern": r"/cameras/failed",
            "supported_methods": ["GET"],
            "method": "get_failed_cameras",
        },
    ]

    def get_cameras(self):
        """Return cameras."""
        self.response_success(
            response=self._vis.data[REGISTERED_DOMAINS].get(CAMERA_DOMAIN, {})
        )

    def get_failed_cameras(self):
        """Return failed cameras."""
        failed_cameras = {}
        for failed_camera in (
            self._vis.data[DOMAIN_FAILED].get(CAMERA_DOMAIN, {}).values()
        ):
            failed_cameras[failed_camera.identifier] = failed_camera.error_instance
        self.response_success(response=failed_cameras)
