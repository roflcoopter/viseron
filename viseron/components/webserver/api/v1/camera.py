"""Camera API Handler."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import cv2
import imutils
import voluptuous as vol

from viseron.components.webserver.api import BaseAPIHandler
from viseron.components.webserver.const import (
    STATUS_ERROR_ENDPOINT_NOT_FOUND,
    STATUS_ERROR_INTERNAL,
)
from viseron.domains.camera import COERCE_INT

if TYPE_CHECKING:
    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)


def _get_snapshot(camera: AbstractCamera, width=None, height=None):
    """Return current frame as jpg bytes."""
    decoded_frame = camera.shared_frames.get_decoded_frame_rgb(camera.current_frame)
    if width and height:
        decoded_frame = cv2.resize(
            decoded_frame, (width, height), interpolation=cv2.INTER_AREA
        )
    elif width or height:
        decoded_frame = imutils.resize(decoded_frame, width, height)

    ret, jpg = cv2.imencode(".jpg", decoded_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
    if ret:
        return ret, jpg.tobytes()
    return ret, False


class CameraAPIHandler(BaseAPIHandler):
    """Handler for API call to get camera snapshot."""

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
    ]

    def get_snapshot(self, camera_identifier):
        """Return camera snapshot."""
        try:
            camera = self._vis.get_registered_camera(camera_identifier.decode())

            if not camera or not camera.current_frame:
                self.response_error(
                    STATUS_ERROR_ENDPOINT_NOT_FOUND,
                    reason=f"Camera {camera_identifier} not found",
                )
                return

            ret, jpg = _get_snapshot(
                camera,
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
