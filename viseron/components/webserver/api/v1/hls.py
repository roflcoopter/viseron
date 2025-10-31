"""API handler for vod."""
from __future__ import annotations

import datetime
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING

import voluptuous as vol
from sqlalchemy import select

from viseron.components.storage.const import (
    TIER_CATEGORY_RECORDER,
    TIER_SUBCATEGORY_SEGMENTS,
)
from viseron.components.storage.models import Files, Recordings
from viseron.components.storage.queries import get_time_period_fragments
from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.domains.camera.fragmenter import (
    Fragment,
    generate_playlist,
    get_available_timespans,
)
from viseron.helpers import client_current_datetime, daterange_to_utc, utcnow
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
                    vol.Optional("date", default=None): vol.Maybe(str),
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
                vol.Any(
                    {
                        vol.Required("time_from"): vol.Coerce(int),
                        vol.Optional("time_to", default=None): vol.Maybe(
                            vol.Coerce(int)
                        ),
                    },
                    {
                        vol.Required("date"): str,
                    },
                )
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
        await self.response_success(response=playlist)

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
            self.utc_offset,
            self.request_arguments["start_timestamp"],
            self.request_arguments["end_timestamp"],
            self.request_arguments["date"],
        )
        if not playlist:
            self.response_error(
                HTTPStatus.NOT_FOUND, "HLS playlist could not be generated"
            )
            return

        self.set_header("Content-Type", "application/x-mpegURL")
        self.set_header("Cache-control", "no-cache, must-revalidate, max-age=0")
        self.set_header("Access-Control-Allow-Origin", "*")
        await self.response_success(response=playlist)

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

        # Convert local start of day to UTC
        if "date" in self.request_arguments:
            _time_from, _time_to = daterange_to_utc(
                self.request_arguments["date"], self.utc_offset
            )
            time_from = _time_from.timestamp()
            time_to = _time_to.timestamp()
        else:
            time_from = self.request_arguments["time_from"]
            time_to = self.request_arguments["time_to"]

        timespans = await self.run_in_executor(
            get_available_timespans,
            self._get_session,
            [camera.identifier],
            time_from,
            time_to,
        )
        await self.response_success(response={"timespans": timespans})


def _get_init_file(
    get_session: Callable[[], Session], camera: AbstractCamera | FailedCamera
) -> str | None:
    """Get the init file for a camera."""
    with get_session() as session:
        stmt = (
            select(Files)
            .distinct(Files.directory)
            .where(Files.camera_identifier == camera.identifier)
            .where(Files.category == TIER_CATEGORY_RECORDER)
            .where(Files.subcategory == TIER_SUBCATEGORY_SEGMENTS)
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
            file.duration,
            file.orig_ctime,
        )
        for file in files
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
    ) + float(files[-1].duration):
        LOGGER.debug("Recording has ended but the last file is not finished yet")
        end = False

    init_file = _get_init_file(get_session, camera)
    if not init_file or not fragments:
        return None

    playlist = generate_playlist(
        fragments,
        f"/files{init_file}",
        end=end,
        file_directive=False,
    )
    return playlist


def update_hls_client(
    hls_client_id: str,
    fragments: list[Fragment],
) -> int:
    """Keep track of HLS client media sequence."""
    media_sequence = 0
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
    return media_sequence


def _generate_playlist_time_period(
    get_session: Callable[[], Session],
    camera: AbstractCamera | FailedCamera,
    hls_client_id: str | None,
    utc_offset: datetime.timedelta,
    start_timestamp: int,
    end_timestamp: int | None = None,
    date: str | None = None,
) -> str | None:
    """Generate the HLS playlist for a time period."""
    end_playlist = False
    if date and end_timestamp is None:
        # If a date is provided, convert to timestamp range
        _, time_to = daterange_to_utc(date, utc_offset)
        end_timestamp = int(time_to.timestamp())
        # If the date is not today, playlist should end
        if date != client_current_datetime(utc_offset).date().isoformat():
            end_playlist = True
    elif end_timestamp is not None:
        end_playlist = True

    files = get_time_period_fragments(
        [camera.identifier], start_timestamp, end_timestamp, get_session
    )
    fragments = []
    for file in files:
        # For tiers other than the first one, we need to alter the path to
        # point to the first tier and then provide the actual tier path as a
        # query parameter.
        # This is to not break the HLS specifications for files that are moved
        # between updates of the playlist
        path: str
        if file.tier_id > 0:
            first_tier_path = camera.tier_base_path(
                0, TIER_CATEGORY_RECORDER, TIER_SUBCATEGORY_SEGMENTS
            )
            path = file.path.replace(
                file.tier_path,
                first_tier_path,
                1,
            )
            path += (
                f"?first_tier_path={first_tier_path}&actual_tier_path={file.tier_path}"
            )
        else:
            path = file.path

        fragments.append(
            Fragment(
                file.filename,
                f"/files{path}",
                file.duration,
                file.orig_ctime,
            )
        )

    media_sequence = (
        update_hls_client(hls_client_id, fragments)
        if end_timestamp is None and hls_client_id
        else 0
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
