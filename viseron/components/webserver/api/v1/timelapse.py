"""Timelapse API handler."""

from __future__ import annotations

import asyncio
import logging
import re
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from viseron.components.storage.const import (
    TIMELAPSE_SEGMENT_ENCODER,
    TIMELAPSE_SEGMENT_FRAMES,
    TIMELAPSE_STREAM_FPS,
)
from viseron.components.storage.queries import (
    TimelapseFrame,
    get_timelapse_days,
    get_timelapse_frames,
    get_timelapse_summary,
)
from viseron.components.storage.timelapse_segments import (
    SegmentRequest,
    TimelapseSegmentBusyError,
    TimelapseSegmentError,
    stream_size,
)
from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.const import (
    TIMELAPSE_DEFAULT_MAX_FRAMES,
    TIMELAPSE_MAX_FRAMES,
    TIMELAPSE_MAX_STREAM_DIMENSION,
    TIMELAPSE_STREAM_MAX_WIDTH,
)
from viseron.helpers.validators import TIMESTAMP, value_even

if TYPE_CHECKING:
    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)


def _end_after_start(value: dict[str, Any]) -> dict[str, Any]:
    if value["end"] <= value["start"]:
        raise vol.Invalid("end must be after start")
    return value


# 15 hex digits keep keys below the BIGINT limit, see file_key_handler.MAX_FILE_KEY
FILE_KEYS_PATTERN = re.compile(r"[0-9a-f]{1,15}(,[0-9a-f]{1,15})*")


def _file_keys(value: str) -> tuple[int, ...]:
    if not FILE_KEYS_PATTERN.fullmatch(value):
        raise vol.Invalid("keys must be comma separated hexadecimal file keys")
    keys = tuple(int(key, 16) for key in value.split(","))
    if len(keys) > TIMELAPSE_SEGMENT_FRAMES:
        raise vol.Invalid(f"at most {TIMELAPSE_SEGMENT_FRAMES} keys are allowed")
    return keys


STREAM_DIMENSION = vol.All(
    vol.Coerce(int), vol.Range(min=2, max=TIMELAPSE_MAX_STREAM_DIMENSION), value_even
)


def _read_segment(path: str) -> bytes:
    with open(path, "rb") as file:
        return file.read()


class TimelapseAPIHandler(BaseAPIHandler):
    """API handler for timelapse frames."""

    routes = [
        {
            "path_pattern": r"/timelapse",
            "supported_methods": ["GET"],
            "method": "get_timelapse_summary",
        },
        {
            "path_pattern": r"/timelapse/(?P<camera_identifier>[A-Za-z0-9_]+)",
            "supported_methods": ["GET"],
            "method": "get_timelapse_frames",
            "request_arguments_schema": vol.Schema(
                vol.All(
                    {
                        vol.Required("start"): TIMESTAMP,
                        vol.Required("end"): TIMESTAMP,
                        vol.Optional(
                            "max_frames", default=TIMELAPSE_DEFAULT_MAX_FRAMES
                        ): vol.All(
                            vol.Coerce(int),
                            vol.Range(min=1, max=TIMELAPSE_MAX_FRAMES),
                        ),
                    },
                    _end_after_start,
                )
            ),
        },
        {
            "path_pattern": (
                r"/timelapse/(?P<camera_identifier>[A-Za-z0-9_]+)/dates_of_interest"
            ),
            "supported_methods": ["GET"],
            "method": "get_timelapse_dates_of_interest",
        },
        {
            "path_pattern": r"/timelapse/(?P<camera_identifier>[A-Za-z0-9_]+)/segment",
            "supported_methods": ["GET"],
            "method": "get_timelapse_segment",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Required("keys"): vol.All(str, _file_keys),
                    vol.Required("start_frame"): vol.All(
                        vol.Coerce(int), vol.Range(min=0)
                    ),
                    vol.Required("width"): STREAM_DIMENSION,
                    vol.Required("height"): STREAM_DIMENSION,
                }
            ),
        },
    ]

    def _frame(self, camera_identifier: str, frame: TimelapseFrame) -> dict[str, Any]:
        return {
            "file_key": frame.file_key,
            "timestamp": frame.orig_ctime.timestamp(),
            # Served by file key, which does not change when the frame moves tier
            "path": f"{self.get_subpath()}/file/{camera_identifier}/{frame.file_key:x}",
        }

    def _get_timelapse_camera(self, camera_identifier: str) -> AbstractCamera | None:
        """Return the camera if the user can access it and timelapse is enabled."""
        camera = self.get_camera(camera_identifier)
        if camera is None or camera.timelapse_folder is None:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Timelapse for camera {camera_identifier} not found",
            )
            return None
        return camera

    async def get_timelapse_summary(self) -> None:
        """Get a timelapse summary for every camera with timelapse enabled."""
        camera_identifiers = [
            camera_identifier
            for camera_identifier, camera in (self.get_cameras() or {}).items()
            if camera.timelapse_folder is not None
        ]
        summary = await self.run_in_executor(
            get_timelapse_summary, camera_identifiers, self._get_session
        )
        await self.response_success(
            response={
                "cameras": {
                    camera_identifier: {
                        "camera_identifier": camera_identifier,
                        "count": camera_summary.count,
                        "first_timestamp": camera_summary.first.timestamp()
                        if camera_summary.first
                        else None,
                        "last_timestamp": camera_summary.last.timestamp()
                        if camera_summary.last
                        else None,
                        "latest_frame": self._frame(
                            camera_identifier, camera_summary.latest_frame
                        )
                        if camera_summary.latest_frame
                        else None,
                    }
                    for camera_identifier, camera_summary in summary.items()
                }
            }
        )

    async def get_timelapse_frames(self, camera_identifier: str) -> None:
        """Get the timelapse frames of a camera in a time range."""
        camera = self._get_timelapse_camera(camera_identifier)
        if camera is None:
            return

        start = self.request_arguments["start"]
        end = self.request_arguments["end"]
        frames = await self.run_in_executor(
            get_timelapse_frames,
            camera.identifier,
            start,
            end,
            self.request_arguments["max_frames"],
            self._get_session,
        )
        size = await self.run_in_executor(
            stream_size,
            camera.identifier,
            frames.frames,
            self._get_session,
            TIMELAPSE_STREAM_MAX_WIDTH,
        )
        await self.response_success(
            response={
                "camera_identifier": camera.identifier,
                "start": start,
                "end": end,
                "step": frames.step,
                "total": frames.total,
                "stream": {
                    "fps": TIMELAPSE_STREAM_FPS,
                    "segment_frames": TIMELAPSE_SEGMENT_FRAMES,
                    "width": size[0],
                    "height": size[1],
                }
                if size
                else None,
                "frames": [
                    self._frame(camera.identifier, frame) for frame in frames.frames
                ],
            }
        )

    async def get_timelapse_dates_of_interest(self, camera_identifier: str) -> None:
        """Get the number of timelapse frames per day in the client's timezone."""
        camera = self._get_timelapse_camera(camera_identifier)
        if camera is None:
            return

        days = await self.run_in_executor(
            get_timelapse_days, camera.identifier, self.utc_offset, self._get_session
        )
        await self.response_success(
            response={
                "dates_of_interest": {
                    day: {"frames": count} for day, count in days.items()
                }
            }
        )

    async def get_timelapse_segment(self, camera_identifier: str) -> None:
        """Get an HLS segment of timelapse frames, encoding it if needed."""
        camera = self._get_timelapse_camera(camera_identifier)
        if camera is None:
            return

        request = SegmentRequest(
            camera_identifier=camera.identifier,
            file_keys=self.request_arguments["keys"],
            start_frame=self.request_arguments["start_frame"],
            width=self.request_arguments["width"],
            height=self.request_arguments["height"],
        )
        try:
            future = self._vis.data[TIMELAPSE_SEGMENT_ENCODER].get(
                request, self._get_session
            )
        except TimelapseSegmentBusyError:
            self.set_header("Retry-After", "5")
            self.response_error(
                HTTPStatus.SERVICE_UNAVAILABLE,
                reason="Too many timelapse segments are being encoded",
            )
            return

        try:
            # shield: the encode future is shared by every request for this
            # segment, so cancelling this request must not cancel it for others
            path = await asyncio.shield(asyncio.wrap_future(future))
        except TimelapseSegmentError as error:
            LOGGER.error("Failed to encode timelapse segment: %s", error)
            self.response_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                reason="Failed to encode timelapse segment",
            )
            return

        await self.response_success(
            response=await self.run_in_executor(_read_segment, path),
            # The URL names the exact frames, so the segment never changes
            headers={
                "Content-Type": "video/mp2t",
                "Cache-Control": "private, max-age=31536000, immutable",
            },
        )
