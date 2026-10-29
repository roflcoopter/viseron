"""API handler for vod."""

from __future__ import annotations

import datetime
import logging
import os
from dataclasses import dataclass
from http import HTTPStatus
from math import ceil
from typing import TYPE_CHECKING

import voluptuous as vol
from sqlalchemy import func, select

from viseron.components.storage.const import (
    TIER_CATEGORY_RECORDER,
    TIER_SUBCATEGORY_SEGMENTS,
)
from viseron.components.storage.models import Files, Recordings
from viseron.components.storage.queries import get_time_period_fragments
from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.const import CAMERA_SEGMENT_DURATION, HLS_SKIP_BOUNDARY_TARGET_DURATIONS
from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.fragmenter import (
    Fragment,
    generate_playlist,
    get_available_timespans,
)
from viseron.helpers import client_current_datetime, daterange_to_utc, utcnow
from viseron.helpers.fixed_size_dict import FixedSizeDict

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

    from viseron.domains.camera import FailedCamera

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


def count_matching_fragments(
    previous_list: list[Fragment], current_list: list[Fragment]
) -> int:
    """Count the leading Fragments that are the same in both lists."""
    count = 0
    for previous, current in zip(previous_list, current_list):
        if previous.filename != current.filename:
            break
        count += 1
    return count


@dataclass
class HlsClient:
    """Dataclass for HLS client to keep track of removed files in live playlists."""

    client_id: str
    fragments: list[Fragment]
    media_sequence: int
    target_duration: int


class HlsAPIHandler(BaseAPIHandler):
    """API handler for HLS."""

    hls_client_ids: FixedSizeDict[str, HlsClient] = FixedSizeDict(maxlen=500)

    routes = [
        {
            "path_pattern": (
                r"/hls/(?P<camera_identifier>[A-Za-z0-9_]+)/"
                r"(?P<recording_id>[0-9]+)/index.m3u8"
            ),
            "supported_methods": ["GET"],
            "method": "get_recording_hls_playlist",
            "allow_token_parameter": True,
            "request_arguments_schema": vol.Schema(
                {
                    vol.Optional("_HLS_skip", default=None): vol.Maybe(
                        vol.In(["YES", "v2"])
                    ),
                }
            ),
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
                    vol.Optional("_HLS_skip", default=None): vol.Maybe(
                        vol.In(["YES", "v2"])
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

        hls_client_id = self.request.headers.get("Hls-Client-Id", None)
        subpath = self.get_subpath()
        playlist = await self.run_in_executor(
            _generate_playlist,
            self._get_session,
            hls_client_id,
            camera,
            recording_id,
            subpath,
            self.request_arguments["_HLS_skip"] is not None,
        )
        if not playlist:
            self.response_error(
                HTTPStatus.NOT_FOUND, f"Recording with id {recording_id} not found"
            )
            return

        self.set_header("Content-Type", "application/x-mpegURL")
        self.set_header("Cache-Control", "no-cache")
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
        subpath = self.get_subpath()
        playlist = await self.run_in_executor(
            _generate_playlist_time_period,
            self._get_session,
            camera,
            hls_client_id,
            self.utc_offset,
            self.request_arguments["start_timestamp"],
            self.request_arguments["end_timestamp"],
            self.request_arguments["date"],
            subpath,
            self.request_arguments["_HLS_skip"] is not None,
        )
        if not playlist:
            self.response_error(
                HTTPStatus.NOT_FOUND, "HLS playlist could not be generated"
            )
            return

        self.set_header("Content-Type", "application/x-mpegURL")
        self.set_header("Cache-control", "no-cache, must-revalidate, max-age=0")
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
    # Normally in the first tier, so avoid querying every tier on each playlist poll
    if isinstance(camera, AbstractCamera):
        init_file = os.path.join(camera.segments_folder, "init.mp4")
        if os.path.exists(init_file):
            return init_file

    with get_session() as session:
        stmt = (
            select(Files.directory)
            .where(Files.camera_identifier == camera.identifier)
            .where(Files.category == TIER_CATEGORY_RECORDER)
            .where(Files.subcategory == TIER_SUBCATEGORY_SEGMENTS)
            .group_by(Files.directory)
            .order_by(func.min(Files.tier_id), func.max(Files.created_at).desc())
        )
        directories = session.execute(stmt).scalars().all()

    for directory in directories:
        init_file = os.path.join(directory, "init.mp4")
        if os.path.exists(init_file):
            return init_file
    LOGGER.error(f"Could not find init.mp4 file for camera {camera.identifier}")
    return None


def get_target_duration(fragments: list[Fragment]) -> int:
    """Get the target duration for HLS playlist."""
    target_duration = 0
    if fragments:
        target_duration = ceil(max(f.duration for f in fragments))
    target_duration = max(target_duration, CAMERA_SEGMENT_DURATION)
    return target_duration


def update_hls_client(
    hls_client_id: str,
    fragments: list[Fragment],
) -> tuple[HlsClient, int]:
    """Keep track of HLS client media sequence.

    Only call this for playlists that are returned to the client, since the fragments
    are stored as the client's previous playlist.
    Returns the client and the number of leading fragments it already received.
    """
    hls_client = HlsAPIHandler.hls_client_ids.get(hls_client_id, None)
    if hls_client:
        removed = count_files_removed(hls_client.fragments, fragments)
        received = count_matching_fragments(hls_client.fragments[removed:], fragments)
        hls_client.fragments = fragments
        hls_client.media_sequence += removed
        return hls_client, received

    hls_client = HlsClient(
        client_id=hls_client_id,
        fragments=fragments,
        media_sequence=0,
        target_duration=get_target_duration(fragments),
    )
    HlsAPIHandler.hls_client_ids[hls_client_id] = hls_client
    return hls_client, 0


def files_to_fragments(subpath: str, files: list) -> list[Fragment]:
    """Create fragments that reference segments by their file key.

    Segment URIs must not change between updates of a playlist, and the file key
    stays the same when a segment moves to another tier.
    """
    return [
        Fragment(
            file.filename,
            # file_key is converted to a hexadecimal string in the URL
            f"{subpath}/file/{file.camera_identifier}/{file.file_key:x}",
            file.duration,
            file.orig_ctime,
        )
        for file in files
    ]


def _render_client_playlist(
    fragments: list[Fragment],
    init_file: str,
    hls_client_id: str | None,
    *,
    skip_requested: bool,
    end: bool,
) -> str:
    """Render the playlist with the media sequence and delta updates of a client."""
    if hls_client_id is None:
        return generate_playlist(fragments, init_file, end=end, file_directive=False)

    hls_client, received = update_hls_client(hls_client_id, fragments)
    return generate_playlist(
        fragments,
        init_file,
        media_sequence=hls_client.media_sequence,
        target_duration=hls_client.target_duration,
        end=end,
        file_directive=False,
        can_skip_until=hls_client.target_duration * HLS_SKIP_BOUNDARY_TARGET_DURATIONS,
        # The client restores skipped segments from its previous playlist, which
        # new or evicted clients lack and stale clients only partially have
        max_skipped_segments=received if skip_requested else 0,
    )


def _generate_playlist(
    get_session: Callable[[], Session],
    hls_client_id: str | None,
    camera: AbstractCamera | FailedCamera,
    recording_id: int,
    subpath: str,
    skip_requested: bool = False,
) -> str | None:
    """Generate the HLS playlist for a recording."""
    now = utcnow()

    with get_session() as session:
        stmt = (
            select(Recordings)
            .where(Recordings.id == recording_id)
            .where(Recordings.camera_identifier == camera.identifier)
        )
        recording = session.execute(stmt).scalar()
        if recording is None:
            return None

    files = recording.get_fragments(
        camera.recorder.lookback,
        get_session,
        now=now,
    )
    fragments = files_to_fragments(subpath, files)

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

    return _render_client_playlist(
        fragments,
        f"{subpath}/files{init_file}",
        hls_client_id,
        skip_requested=skip_requested,
        end=end,
    )


def _generate_playlist_time_period(
    get_session: Callable[[], Session],
    camera: AbstractCamera | FailedCamera,
    hls_client_id: str | None,
    utc_offset: datetime.timedelta,
    start_timestamp: int,
    end_timestamp: int | None = None,
    date: str | None = None,
    subpath: str = "",
    skip_requested: bool = False,
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
    fragments = files_to_fragments(subpath, files)

    init_file = _get_init_file(get_session, camera)
    if not init_file:
        return None

    return _render_client_playlist(
        fragments,
        f"{subpath}/files{init_file}",
        hls_client_id,
        skip_requested=skip_requested,
        end=end_playlist,
    )
