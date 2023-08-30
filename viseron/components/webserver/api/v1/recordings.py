"""Recordings API Handler."""
from __future__ import annotations

import logging
from http import HTTPStatus
from typing import TYPE_CHECKING

import voluptuous as vol

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.helpers.validators import request_argument_bool, request_argument_no_value

if TYPE_CHECKING:
    from viseron.domains.camera import AbstractCamera, FailedCamera

LOGGER = logging.getLogger(__name__)

LATEST_DAILY_GROUP = "latest_daily"
LATEST_DAILY_MSG = "'daily' must be used together with 'latest'"


class RecordingsAPIHandler(BaseAPIHandler):
    """Handler for API calls related to recordings."""

    routes = [
        {
            "path_pattern": r"/recordings",
            "supported_methods": ["GET"],
            "method": "get_recordings",
            "request_arguments_schema": vol.Schema(
                vol.Any(
                    {
                        vol.Inclusive(
                            "latest",
                            LATEST_DAILY_GROUP,
                            default=False,
                            msg=LATEST_DAILY_MSG,
                        ): request_argument_no_value,
                        vol.Inclusive(
                            "daily",
                            LATEST_DAILY_GROUP,
                            default=False,
                            msg=LATEST_DAILY_MSG,
                        ): request_argument_no_value,
                        vol.Optional("failed", default=False): request_argument_bool,
                    },
                    {
                        vol.Optional(
                            "latest", default=False
                        ): request_argument_no_value,
                        vol.Optional("failed", default=False): request_argument_bool,
                    },
                ),
            ),
        },
        {
            "path_pattern": (
                r"/recordings/(?P<camera_identifier>[A-Za-z0-9_]+)"
                r"/(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})"
            ),
            "supported_methods": ["GET"],
            "method": "get_recordings_camera",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Optional("latest", default=False): request_argument_no_value,
                    vol.Optional("failed", default=False): request_argument_bool,
                },
            ),
        },
        {
            "path_pattern": r"/recordings/(?P<camera_identifier>[A-Za-z0-9_]+)",
            "supported_methods": ["GET"],
            "method": "get_recordings_camera",
            "request_arguments_schema": vol.Schema(
                vol.Any(
                    {
                        vol.Inclusive(
                            "latest",
                            LATEST_DAILY_GROUP,
                            default=False,
                            msg=LATEST_DAILY_MSG,
                        ): request_argument_no_value,
                        vol.Inclusive(
                            "daily",
                            LATEST_DAILY_GROUP,
                            default=False,
                            msg=LATEST_DAILY_MSG,
                        ): request_argument_no_value,
                        vol.Optional("failed", default=False): request_argument_bool,
                    },
                    {
                        vol.Optional(
                            "latest", default=False
                        ): request_argument_no_value,
                        vol.Optional("failed", default=False): request_argument_bool,
                    },
                ),
            ),
        },
        {
            "path_pattern": (
                r"/recordings/(?P<camera_identifier>[A-Za-z0-9_]+)"
                r"/(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})"
                r"/(?P<filename>.*\..*)"
            ),
            "supported_methods": ["DELETE"],
            "method": "delete_recording",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Optional("failed", default=False): request_argument_bool,
                },
            ),
        },
        {
            "path_pattern": (
                r"/recordings/(?P<camera_identifier>[A-Za-z0-9_]+)"
                r"/(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})"
            ),
            "supported_methods": ["DELETE"],
            "method": "delete_recording",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Optional("failed", default=False): request_argument_bool,
                },
            ),
        },
        {
            "path_pattern": r"/recordings/(?P<camera_identifier>[A-Za-z0-9_]+)",
            "supported_methods": ["DELETE"],
            "method": "delete_recording",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Optional("failed", default=False): request_argument_bool,
                },
            ),
        },
    ]

    async def get_recordings(self) -> None:
        """Get recordings for all cameras."""
        cameras = self._get_cameras()

        if not cameras:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason="No cameras found",
            )
            return

        recordings = {}
        for camera in cameras.values():
            if self.request_arguments["latest"] and self.request_arguments.get(
                "daily", False
            ):
                recordings[camera.identifier] = await self.run_in_executor(
                    camera.recorder.get_latest_recording_daily
                )
                continue
            if self.request_arguments["latest"]:
                recordings[camera.identifier] = await self.run_in_executor(
                    camera.recorder.get_latest_recording
                )
                continue
            recordings[camera.identifier] = await self.run_in_executor(
                camera.recorder.get_recordings
            )

        self.response_success(response=recordings)
        return

    async def get_recordings_camera(
        self, camera_identifier: str, date: str | None = None
    ) -> None:
        """Get recordings for a single camera."""
        camera: AbstractCamera | FailedCamera = self._get_camera(
            camera_identifier, failed=self.request_arguments["failed"]
        )

        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        if self.request_arguments["latest"] and self.request_arguments.get(
            "daily", False
        ):
            self.response_success(
                response=await self.run_in_executor(
                    camera.recorder.get_latest_recording_daily
                )
            )
            return

        if self.request_arguments["latest"]:
            self.response_success(
                response=await self.run_in_executor(
                    camera.recorder.get_latest_recording, date
                )
            )
            return

        self.response_success(
            response=await self.run_in_executor(camera.recorder.get_recordings, date)
        )
        return

    def delete_recording(
        self,
        camera_identifier: str,
        date: str | None = None,
        filename: str | None = None,
    ) -> None:
        """Delete recording(s)."""
        camera = self._get_camera(
            camera_identifier, failed=self.request_arguments["failed"]
        )

        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        # Try to delete recording
        if camera.recorder.delete_recording(date, filename):
            self.response_success()
            return
        self.response_error(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            reason=f"Failed to delete recording. Date={date} filename={filename}",
        )
        return
