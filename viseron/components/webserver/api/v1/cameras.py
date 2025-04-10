"""Cameras API Handler."""
from __future__ import annotations

import logging

from viseron.components.webserver.api.handlers import BaseAPIHandler

LOGGER = logging.getLogger(__name__)


class CamerasAPIHandler(BaseAPIHandler):
    """Handler for API calls related to cameras."""

    routes = [
        {
            "path_pattern": r"/cameras",
            "supported_methods": ["GET"],
            "method": "get_cameras_endpoint",
        },
        {
            "path_pattern": r"/cameras/failed",
            "supported_methods": ["GET"],
            "method": "get_failed_cameras_endpoint",
        },
    ]

    async def get_cameras_endpoint(self) -> None:
        """Return cameras."""
        await self.response_success(response=self._get_cameras())

    async def get_failed_cameras_endpoint(self) -> None:
        """Return failed cameras."""
        await self.response_success(response=self._get_failed_cameras())
