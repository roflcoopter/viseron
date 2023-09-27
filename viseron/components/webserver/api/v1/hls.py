"""API handler for vod."""
from __future__ import annotations

import datetime
import logging
import os
from http import HTTPStatus
from typing import TYPE_CHECKING, Callable

from sqlalchemy import select

from viseron.components.storage.models import Recordings
from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.domains.camera.const import CONFIG_LOOKBACK, CONFIG_RECORDER
from viseron.domains.camera.fragmenter import Fragment, generate_playlist
from viseron.helpers import utcnow

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)


class HlsAPIHandler(BaseAPIHandler):
    """API handler for HLS."""

    routes = [
        {
            "path_pattern": (
                r"/hls/(?P<camera_identifier>[A-Za-z0-9_]+)/"
                r"(?P<recording_id>[0-9]+)/index.m3u8"
            ),
            "supported_methods": ["GET"],
            "method": "get_recording_hls_playlist",
        },
    ]

    async def get_recording_hls_playlist(
        self, camera_identifier: str, recording_id: int
    ):
        """Get the HLS playlist for a recording."""
        camera = self._get_camera(camera_identifier)

        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        playlist = await self.run_in_executor(
            _generate_playlist, self._get_session, camera, recording_id
        )
        if not playlist:
            self.response_error(
                HTTPStatus.NOT_FOUND, f"Recording with id {recording_id} not found"
            )
            return

        self.set_header("Content-Type", "application/x-mpegURL")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Access-Control-Allow-Origin", "*")
        self.response_success(response=playlist)


def _generate_playlist(
    get_session: Callable[[], Session],
    camera: AbstractCamera,
    recording_id: int,
) -> str | None:
    """Generate the HLS playlist for a recording."""
    now = utcnow()

    with get_session() as session:
        stmt = select(Recordings).where(Recordings.id == recording_id)
        recording = session.execute(stmt).scalar()
        if recording is None:
            return None

    files = recording.get_fragments(
        camera.config[CONFIG_RECORDER][CONFIG_LOOKBACK],
        get_session,
        now=now,
    )
    fragments = [
        Fragment(
            f"/files{file.path}",
            float(
                file.meta["m3u8"]["EXTINF"],
            ),
        )
        for file in files
        if file.meta.get("m3u8", False,).get(
            "EXTINF",
            False,
        )
    ]

    end: bool = True
    # Recording has not ended yet
    if recording.end_time is None:
        LOGGER.debug("Recording has not ended yet")
        end = False
    # End the playlist if the recording ended more than a minute ago
    # Prevents infinitely waiting for the last file to finish if it is missing
    # for some reason
    elif recording.end_time < now - datetime.timedelta(minutes=1):
        LOGGER.debug("Recording ended more than a minute ago")
        end = True
    # Recording has ended but the last file is not finished yet
    elif len(files) > 0 and recording.end_time.timestamp() > float(
        files[-1].filename.split(".")[0]
    ) + float(files[-1].meta["m3u8"]["EXTINF"]):
        LOGGER.debug("Recording has ended but the last file is not finished yet")
        end = False

    playlist = generate_playlist(
        fragments,
        f"/files{os.path.join(camera.segments_folder,'init.mp4')}",
        end=end,
        file_directive=False,
    )
    return playlist
