"""Camera API Handler."""
from __future__ import annotations

import logging
from http import HTTPStatus

import voluptuous as vol

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.helpers.validators import request_argument_bool

LOGGER = logging.getLogger(__name__)


class CameraAPIHandler(BaseAPIHandler):
    """Handler for API calls related to a camera."""

    routes = [
        {
            "requires_auth": False,
            "requires_camera_token": True,
            "path_pattern": r"/camera/(?P<camera_identifier>[A-Za-z0-9_]+)/snapshot",
            "supported_methods": ["GET"],
            "method": "get_snapshot",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Optional("rand", default=None): vol.Maybe(str),
                    vol.Optional("width", default=None): vol.Maybe(vol.Coerce(int)),
                    vol.Optional("height", default=None): vol.Maybe(vol.Coerce(int)),
                    vol.Optional("access_token", default=None): vol.Maybe(str),
                },
            ),
        },
        {
            "path_pattern": r"/camera/(?P<camera_identifier>[A-Za-z0-9_]+)",
            "supported_methods": ["GET"],
            "method": "get_camera",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Optional("failed", default=False): request_argument_bool,
                },
            ),
        },
    ]

    def get_snapshot(self, camera_identifier: str):
        """Return camera snapshot."""
        camera = self._get_camera(camera_identifier)

        if not camera or not camera.current_frame:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        ret, jpg = camera.get_snapshot(
            camera.current_frame,
            self.request_arguments["width"],
            self.request_arguments["height"],
        )

        if ret:
            self.response_success(response=jpg, headers={"Content-Type": "image/jpeg"})
            return
        self.response_error(
            HTTPStatus.INTERNAL_SERVER_ERROR, reason="Could not fetch camera snapshot"
        )
        return

    def get_camera(self, camera_identifier: str):
        """Return camera."""
        camera = self._get_camera(
            camera_identifier, failed=self.request_arguments["failed"]
        )

        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        self.response_success(response=camera.as_dict())
        return
