"""Camera API Handler."""
from __future__ import annotations

import logging

import voluptuous as vol

from viseron.components.webserver.api import BaseAPIHandler
from viseron.components.webserver.const import (
    STATUS_ERROR_ENDPOINT_NOT_FOUND,
    STATUS_ERROR_INTERNAL,
)
from viseron.domains.camera import COERCE_INT
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.exceptions import DomainNotRegisteredError

LOGGER = logging.getLogger(__name__)


class CameraAPIHandler(BaseAPIHandler):
    """Handler for API calls related to a camera."""

    routes = [
        {
            "path_pattern": r"/camera/(?P<camera_identifier>[A-Za-z0-9_]+)/snapshot",
            "supported_methods": ["GET"],
            "method": "get_snapshot",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Optional("rand", default=None): vol.Maybe(str),
                    vol.Optional("width", default=None): vol.Maybe(COERCE_INT),
                    vol.Optional("height", default=None): vol.Maybe(COERCE_INT),
                },
            ),
        },
        {
            "path_pattern": r"/camera/(?P<camera_identifier>[A-Za-z0-9_]+)",
            "supported_methods": ["GET"],
            "method": "get_camera",
        },
    ]

    def _get_camera(self, camera_identifier: str):
        """Get camera instance."""
        try:
            return self._vis.get_registered_domain(CAMERA_DOMAIN, camera_identifier)
        except DomainNotRegisteredError:
            return None

    def get_snapshot(self, camera_identifier: bytes):
        """Return camera snapshot."""

        try:
            camera = self._get_camera(camera_identifier.decode())

            if not camera or not camera.current_frame:
                self.response_error(
                    STATUS_ERROR_ENDPOINT_NOT_FOUND,
                    reason=f"Camera {camera_identifier.decode()} not found",
                )
                return

            ret, jpg = camera.get_snapshot(
                camera.current_frame,
                self.request_arguments["width"],
                self.request_arguments["height"],
            )

            if ret:
                self.response_success(
                    response=jpg, headers={"Content-Type": "image/jpeg"}
                )
                return
            self.response_error(
                STATUS_ERROR_INTERNAL, reason="Could not fetch camera snapshot"
            )
            return
        except Exception as error:  # pylint: disable=broad-except
            LOGGER.error(
                f"Error in API {self.__class__.__name__}.{self.route['method']}: "
                f"{str(error)}",
                exc_info=True,
            )
            self.response_error(STATUS_ERROR_INTERNAL, reason=str(error))

    def get_camera(self, camera_identifier: bytes):
        """Return camera."""
        try:
            camera = self._get_camera(camera_identifier.decode())

            if not camera:
                self.response_error(
                    STATUS_ERROR_ENDPOINT_NOT_FOUND,
                    reason=f"Camera {camera_identifier.decode()} not found",
                )
                return

            self.response_success(camera.as_dict())
            return
        except Exception as error:  # pylint: disable=broad-except
            LOGGER.error(
                f"Error in API {self.__class__.__name__}.{self.route['method']}: "
                f"{str(error)}"
            )
            self.response_error(STATUS_ERROR_INTERNAL, reason=str(error))
