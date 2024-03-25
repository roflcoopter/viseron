"""API handler for vod."""
from __future__ import annotations

import datetime
import logging
import os
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Callable

import voluptuous as vol
from sqlalchemy import Row, select

from viseron.components.storage.models import Files, Recordings
from viseron.components.storage.queries import get_time_period_fragments
from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.const import CAMERA_SEGMENT_DURATION
from viseron.domains.camera.fragmenter import Fragment, generate_playlist
from viseron.helpers import utcnow
from viseron.helpers.fixed_size_dict import FixedSizeDict

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from viseron.domains.camera import AbstractCamera, FailedCamera

LOGGER = logging.getLogger(__name__)


def count_files_removed(
    previous_list: list[Fragment], current_list: list[Fragment]
) -> int:
    """Count the number of Fragments removed from the previous playlist."""
    if not previous_list:
        return 0
    if not current_list:
        return len(previous_list)

    index = 0
    for index, file in enumerate(previous_list):
        if file.filename == current_list[0].filename:
            return index
    return index + 1


@dataclass
class HlsClient:
    """Dataclass for HLS client to keep track of removed files in live playlists."""

    client_id: str
    fragments: list[Fragment]
    media_sequence: int


class HlsAPIHandler(BaseAPIHandler):
    """API handler for HLS."""

    hls_client_ids: FixedSizeDict[str, HlsClient] = FixedSizeDict(maxlen=10)

    routes = [
        {
            "path_pattern": (
                r"/hls/(?P<camera_identifier>[A-Za-z0-9_]+)/"
                r"(?P<recording_id>[0-9]+)/index.m3u8"
            ),
            "supported_methods": ["GET"],
            "method": "get_recording_hls_playlist",
            "allow_token_parameter": True,
        },
        {
            "path_pattern": (r"/hls/(?P<camera_identifier>[A-Za-z0-9_]+)/index.m3u8"),
            "supported_methods": ["GET"],
            "method": "get_hls_playlist_time_period",
            "allow_token_parameter": True,
            "request_arguments_schema": vol.Schema(
                {
                    vol.Required("start_timestamp"): vol.Coerce(int),
                    vol.Optional("end_timestamp", default=None): vol.Maybe(
                        vol.Coerce(int)
                    ),
                }
            ),
        },
        {
            "path_pattern": (
                r"/hls/(?P<camera_identifier>[A-Za-z0-9_]+)/available_timespans"
            ),
            "supported_methods": ["GET"],
            "method": "get_available_timespans",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Required("time_from"): vol.Coerce(int),
                    vol.Optional("time_to", default=None): vol.Maybe(vol.Coerce(int)),
                }
            ),
        },
    ]

    async def get_recording_hls_playlist(
        self, camera_identifier: str, recording_id: int
    ):
        """Get the HLS playlist for a recording."""
        camera = self._get_camera(camera_identifier, failed=True)

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

    async def get_hls_playlist_time_period(
        self,
        camera_identifier: str,
    ):
        """Get the HLS playlist for a time period."""
        camera = self._get_camera(camera_identifier, failed=True)

        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        hls_client_id = self.request.headers.get("Hls-Client-Id", None)
        playlist = await self.run_in_executor(
            _generate_playlist_time_period,
            self._get_session,
            camera,
            hls_client_id,
            self.request_arguments["start_timestamp"],
            self.request_arguments["end_timestamp"],
        )
        if not playlist:
            self.response_error(
                HTTPStatus.NOT_FOUND, "HLS playlist could not be generated"
            )
            return

        self.set_header("Content-Type", "application/x-mpegURL")
        self.set_header("Cache-control", "no-cache, must-revalidate, max-age=0")
        self.set_header("Access-Control-Allow-Origin", "*")
        self.response_success(response=playlist)

    async def get_available_timespans(
        self,
        camera_identifier: str,
    ):
        """Get the available timespans of HLS fragments for a time period."""
        camera = self._get_camera(camera_identifier, failed=True)

        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        timespans = await self.run_in_executor(
            _get_available_timespans,
            self._get_session,
            camera,
            self.request_arguments["time_from"],
            self.request_arguments["time_to"],
        )
        self.response_success(response={"timespans": timespans})


def _get_available_timespans(
    get_session: Callable[[], Session],
    camera: AbstractCamera | FailedCamera,
    time_from: int,
    time_to: int | None = None,
):
    """Get the available timespans of HLS fragments for a time period."""
    files = get_time_period_fragments(
        camera.identifier, time_from, time_to, get_session
    )
    fragments = [
        Fragment(
            file.filename,
            f"/files{file.path}",
            float(
                file.meta["m3u8"]["EXTINF"],
            ),
            file.orig_ctime,
        )
        for file in files
        if file.meta.get("m3u8", {}).get("EXTINF", False)
    ]

    timespans = []
    start = None
    end = None
    for fragment in fragments:
        if start is None:
            start = fragment.creation_time.timestamp()
        if end is None:
            end = fragment.creation_time.timestamp() + fragment.duration
        if fragment.creation_time.timestamp() > end + fragment.duration:
            timespans.append(
                {"start": int(start), "end": int(end), "duration": int(end - start)}
            )
            start = fragment.creation_time.timestamp()
            end = None
        else:
            end = fragment.creation_time.timestamp() + fragment.duration
    if start is not None and end is not None:
        timespans.append(
            {"start": int(start), "end": int(end), "duration": int(end - start)}
        )
    return timespans


def _get_init_file(
    get_session: Callable[[], Session], camera: AbstractCamera | FailedCamera
) -> str | None:
    """Get the init file for a camera."""
    with get_session() as session:
        stmt = (
            select(Files)
            .distinct(Files.directory)
            .where(Files.camera_identifier == camera.identifier)
            .where(Files.category == "recorder")
            .where(Files.subcategory == "segments")
            .order_by(Files.directory, Files.created_at.desc())
        )
        files = session.execute(stmt).scalars().all()

    for file in files:
        if os.path.exists(os.path.join(file.directory, "init.mp4")):
            return os.path.join(file.directory, "init.mp4")
    LOGGER.error(f"Could not find init.mp4 file for camera {camera.identifier}")
    return None


def _generate_playlist(
    get_session: Callable[[], Session],
    camera: AbstractCamera | FailedCamera,
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
        camera.recorder.lookback,
        get_session,
        now=now,
    )
    fragments = [
        Fragment(
            file.filename,
            f"/files{file.path}",
            float(
                file.meta["m3u8"]["EXTINF"],
            ),
            file.orig_ctime,
        )
        for file in files
        if file.meta.get("m3u8", {}).get("EXTINF", False)
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

    init_file = _get_init_file(get_session, camera)
    if not init_file:
        return None

    playlist = generate_playlist(
        fragments,
        f"/files{init_file}",
        end=end,
        file_directive=False,
    )
    return playlist


def _generate_playlist_time_period(
    get_session: Callable[[], Session],
    camera: AbstractCamera | FailedCamera,
    hls_client_id: str | None,
    start_timestamp: int,
    end_timestamp: int | None = None,
) -> str | None:
    """Generate the HLS playlist for a time period."""
    files = get_time_period_fragments(
        camera.identifier, start_timestamp, end_timestamp, get_session
    )
    fragments = []
    prev_file: Row[Any] | None = None
    end_playlist = bool(end_timestamp)
    for file in files:
        # Break if there is a gap in segments
        if prev_file and file.orig_ctime - prev_file.orig_ctime > datetime.timedelta(
            seconds=CAMERA_SEGMENT_DURATION * 3
        ):
            end_playlist = True
            break

        if file.meta.get("m3u8", {}).get("EXTINF", False):
            fragments.append(
                Fragment(
                    file.filename,
                    f"/files{file.path}",
                    float(
                        file.meta["m3u8"]["EXTINF"],
                    ),
                    file.orig_ctime,
                )
            )
            prev_file = file

    media_sequence = 0
    if end_timestamp is None and hls_client_id:
        hls_client = HlsAPIHandler.hls_client_ids.get(hls_client_id, None)
        if hls_client:
            media_sequence = hls_client.media_sequence
            media_sequence += count_files_removed(hls_client.fragments, fragments)
            hls_client.fragments = fragments
            hls_client.media_sequence = media_sequence
        else:
            HlsAPIHandler.hls_client_ids[hls_client_id] = HlsClient(
                hls_client_id, fragments, media_sequence
            )

    init_file = _get_init_file(get_session, camera)
    if not init_file:
        return None

    playlist = generate_playlist(
        fragments,
        f"/files{init_file}",
        media_sequence=media_sequence,
        end=end_playlist,
        file_directive=False,
    )
    return playlist
