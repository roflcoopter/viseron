"""Recordings API Handler."""
from __future__ import annotations

import logging
from http import HTTPStatus
from typing import cast

import voluptuous as vol
from sqlalchemy import select

from viseron.components.storage.const import (
    TIER_CATEGORY_RECORDER,
    TIER_SUBCATEGORY_THUMBNAILS,
)
from viseron.components.storage.models import Files, Recordings
from viseron.components.storage.thumbnails import (
    RecoveredThumbnail,
    recover_recording_thumbnail,
)
from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.api.v1.files import (
    authorize_file_request,
    resolve_file_id,
    serve_resolved_file,
)
from viseron.helpers.validators import request_argument_bool, request_argument_no_value

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
            "path_pattern": (
                r"/recordings/(?P<camera_identifier>[A-Za-z0-9_]+)"
                r"/(?P<recording_id>[0-9]+)/thumbnail"
            ),
            "supported_methods": ["GET"],
            "method": "get_recording_thumbnail",
            "allow_token_parameter": True,
            "requires_auth": False,
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
        {  # Delete a specific recording
            "path_pattern": (
                r"/recordings/(?P<camera_identifier>[A-Za-z0-9_]+)"
                r"/(?P<recording_id>[0-9]+)"
            ),
            "supported_methods": ["DELETE"],
            "method": "delete_recording",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Optional("failed", default=False): request_argument_bool,
                },
            ),
        },
        {  # Delete all recordings for a specific camera and date
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
        {  # Delete all recordings for a specific camera
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

        subpath = self.get_subpath()
        recordings = {}
        for camera in cameras.values():
            if self.request_arguments["latest"] and self.request_arguments.get(
                "daily", False
            ):
                recordings[camera.identifier] = await self.run_in_executor(
                    camera.recorder.get_latest_recording_daily, self.utc_offset, subpath
                )
                continue
            if self.request_arguments["latest"]:
                recordings[camera.identifier] = await self.run_in_executor(
                    camera.recorder.get_latest_recording, self.utc_offset, None, subpath
                )
                continue
            recordings[camera.identifier] = await self.run_in_executor(
                camera.recorder.get_recordings, self.utc_offset, None, subpath
            )

        await self.response_success(response=recordings)
        return

    async def get_recordings_camera(
        self, camera_identifier: str, date: str | None = None
    ) -> None:
        """Get recordings for a single camera."""
        camera = self._get_camera(
            camera_identifier, failed=cast(bool, self.request_arguments["failed"])
        )

        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        subpath = self.get_subpath()
        if self.request_arguments["latest"] and self.request_arguments.get(
            "daily", False
        ):
            await self.response_success(
                response=await self.run_in_executor(
                    camera.recorder.get_latest_recording_daily, self.utc_offset, subpath
                )
            )
            return

        if self.request_arguments["latest"]:
            await self.response_success(
                response=await self.run_in_executor(
                    camera.recorder.get_latest_recording, self.utc_offset, date, subpath
                )
            )
            return

        await self.response_success(
            response=await self.run_in_executor(
                camera.recorder.get_recordings, self.utc_offset, date, subpath
            )
        )
        return

    async def get_recording_thumbnail(
        self, camera_identifier: str, recording_id: str
    ) -> None:
        """Get a recording thumbnail, recovering it when possible."""
        if not await authorize_file_request(self, camera_identifier, failed=True):
            return

        camera = self._get_camera(camera_identifier, failed=True)
        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        recovered_thumbnail = await self.run_in_executor(
            _recover_recording_thumbnail,
            self._get_session,
            self._storage,
            camera,
            int(recording_id),
        )
        if recovered_thumbnail is None:
            self.response_error(HTTPStatus.NOT_FOUND, reason="Thumbnail not found")
            return

        resolved_file = await self.run_in_executor(
            resolve_file_id,
            self._get_session,
            self._storage,
            recovered_thumbnail.file_id,
            frozenset({(TIER_CATEGORY_RECORDER, TIER_SUBCATEGORY_THUMBNAILS)}),
        )
        if resolved_file is None:
            self.response_error(HTTPStatus.NOT_FOUND, reason="Thumbnail not found")
            return

        await serve_resolved_file(self, resolved_file)
        return

    async def delete_recording(
        self,
        camera_identifier: str,
        date: str | None = None,
        recording_id: str | None = None,
    ) -> None:
        """Delete recording(s)."""
        camera = self._get_camera(
            camera_identifier, failed=cast(bool, self.request_arguments["failed"])
        )

        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        # Try to delete recording
        if await self.run_in_executor(
            camera.recorder.delete_recording, self.utc_offset, date, recording_id
        ):
            await self.response_success()
            return
        self.response_error(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            reason=(
                f"Failed to delete recording. Date={date} recording_id={recording_id}"
            ),
        )
        return


def _recover_recording_thumbnail(
    get_session,
    storage,
    camera,
    recording_id: int,
):
    """Recover a recording thumbnail and ensure it has a Files row."""
    with get_session() as session:
        recording = session.execute(
            select(Recordings)
            .where(Recordings.id == recording_id)
            .where(Recordings.camera_identifier == camera.identifier)
        ).scalar_one_or_none()
        if recording is None:
            return None

        thumbnail_path = recording.thumbnail_path
        thumbnail_file_id = recording.thumbnail_file_id

        if thumbnail_file_id is not None:
            file = session.get(Files, thumbnail_file_id)
            if file is not None:
                return RecoveredThumbnail(path=file.path, file_id=thumbnail_file_id)

    if thumbnail_path is None:
        return None

    return recover_recording_thumbnail(
        storage,
        camera,
        recording_id,
        thumbnail_path,
        camera.recorder.lookback,
    )
