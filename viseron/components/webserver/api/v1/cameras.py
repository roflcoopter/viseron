"""Cameras API Handler."""
from __future__ import annotations

import logging

from viseron.components.webserver.api import BaseAPIHandler
from viseron.components.webserver.const import STATUS_ERROR_INTERNAL
from viseron.const import REGISTERED_DOMAINS
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
    ]

    def get_cameras(self):
        """Return cameras."""
        try:
            self.response_success(
                self._vis.data[REGISTERED_DOMAINS].get(CAMERA_DOMAIN, {})
            )
            return
        except Exception as error:  # pylint: disable=broad-except
            LOGGER.error(
                f"Error in API {self.__class__.__name__}.{self.route['method']}: "
                f"{str(error)}"
            )
            self.response_error(STATUS_ERROR_INTERNAL, reason=str(error))
