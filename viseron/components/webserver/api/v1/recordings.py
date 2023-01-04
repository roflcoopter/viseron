"""Recordings API Handler."""
from __future__ import annotations

import logging

from viseron.components.webserver.api import BaseAPIHandler
from viseron.components.webserver.const import (
    STATUS_ERROR_ENDPOINT_NOT_FOUND,
    STATUS_ERROR_INTERNAL,
)

LOGGER = logging.getLogger(__name__)


class RecordingsAPIHandler(BaseAPIHandler):
    """Handler for API calls related to recordings."""

    routes = [
        {
            "path_pattern": (
                r"/recordings/(?P<camera_identifier>[A-Za-z0-9_]+)"
                r"/(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})"
                r"/(?P<filename>.*\..*)"
            ),
            "supported_methods": ["DELETE"],
            "method": "delete_recording",
        },
        {
            "path_pattern": (
                r"/recordings/(?P<camera_identifier>[A-Za-z0-9_]+)"
                r"/(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})"
            ),
            "supported_methods": ["DELETE"],
            "method": "delete_recording",
        },
        {
            "path_pattern": (r"/recordings/(?P<camera_identifier>[A-Za-z0-9_]+)"),
            "supported_methods": ["DELETE"],
            "method": "delete_recording",
        },
    ]

    def delete_recording(
        self, camera_identifier: bytes, date: bytes = None, filename: bytes = None
    ):
        """Delete recording(s)."""
        camera = self._get_camera(camera_identifier.decode())

        if not camera:
            self.response_error(
                STATUS_ERROR_ENDPOINT_NOT_FOUND,
                reason=f"Camera {camera_identifier.decode()} not found",
            )
            return

        # Try to delete recording
        if camera.delete_recording(
            date.decode() if date else date,
            filename.decode() if filename else filename,
        ):
            self.response_success()
            return
        self.response_error(
            STATUS_ERROR_INTERNAL,
            reason=(f"Failed to delete recording. Date={date!r} filename={filename!r}"),
        )
        return
