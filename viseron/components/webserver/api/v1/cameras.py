"""Cameras API Handler."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from viseron.components.webserver.api import BaseAPIHandler
from viseron.components.webserver.const import STATUS_ERROR_INTERNAL
from viseron.const import REGISTERED_CAMERAS

if TYPE_CHECKING:
    from viseron.domains.camera import AbstractCamera

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

    def get_cameras(self, kwargs):
        """Return Viseron config."""
        cameras = {}
        for camera_identifier in self._vis.data[REGISTERED_CAMERAS]:
            camera: AbstractCamera = self._vis.data[REGISTERED_CAMERAS][
                camera_identifier
            ]
            camera_info = {}
            camera_info["identifier"] = camera_identifier
            camera_info["name"] = camera.name
            cameras[camera_identifier] = camera_info
        try:
            self.response_success(cameras)
            return
        except Exception as error:  # pylint: disable=broad-except
            LOGGER.error(
                f"Error in API {self.__class__.__name__}.{kwargs['route']['method']}: "
                f"{str(error)}"
            )
            self.response_error(STATUS_ERROR_INTERNAL, reason=str(error))
