"""API handler for vod."""
from __future__ import annotations

import datetime
import logging
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from itertools import pairwise
from math import ceil
from typing import TYPE_CHECKING

import voluptuous as vol
from sqlalchemy import select

from viseron.components.storage.const import (
    CONFIG_PATH,
    TIER_CATEGORY_RECORDER,
    TIER_SUBCATEGORY_SEGMENTS,
)
from viseron.components.storage.models import (
    FileLocations,
    FileLocationState,
    Files,
    Recordings,
)
from viseron.components.storage.queries import get_time_period_fragments
from viseron.components.storage.util import get_segments_path
from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.api.v1.files import (
    HLS_SEGMENT_FILE_TYPES,
    ResolvedFile,
    authorize_file_request,
    resolve_file_id,
    serve_resolved_file,
)
from viseron.const import CAMERA_SEGMENT_DURATION
from viseron.domains.camera.fragmenter import (
    Fragment,
    discontinuity_in_fragments,
    generate_playlist,
    get_available_timespans,
)
from viseron.helpers import client_current_datetime, daterange_to_utc, utcnow
from viseron.helpers.fixed_size_dict import FixedSizeDict

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from viseron.domains.camera import AbstractCamera, FailedCamera

LOGGER = logging.getLogger(__name__)
HLS_SEGMENT_RESPONSE_WARN_SECONDS = 0.05
HLS_INIT_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")


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


def count_discontinuities_removed(
    previous_list: list[Fragment], current_list: list[Fragment]
) -> int:
    """Count discontinuity boundaries removed from the previous playlist."""
    if not previous_list:
        return 0
    if not current_list:
        return sum(
            1
            for previous_fragment, fragment in pairwise(previous_list)
            if discontinuity_in_fragments(previous_fragment, fragment)
        )

    for index, file in enumerate(previous_list):
        if file.filename == current_list[0].filename:
            removed_files = previous_list[: index + 1]
            return sum(
                1
                for previous_fragment, fragment in pairwise(removed_files)
                if discontinuity_in_fragments(previous_fragment, fragment)
            )

    removed_count = sum(
        1
        for previous_fragment, fragment in pairwise(previous_list)
        if discontinuity_in_fragments(previous_fragment, fragment)
    )
    if (
        previous_list[-1].creation_time < current_list[0].creation_time
        and discontinuity_in_fragments(previous_list[-1], current_list[0])
    ):
        removed_count += 1
    return removed_count


@dataclass
class HlsClient:
    """Dataclass for HLS client to keep track of removed files in live playlists."""

    client_id: str
    fragments: list[Fragment]
    media_sequence: int
    discontinuity_sequence: int
    target_duration: int


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
        {
            "path_pattern": r"/hls/segments/(?P<file_id>[0-9]+).m4s",
            "supported_methods": ["GET"],
            "method": "get_hls_segment",
            "allow_token_parameter": True,
            "requires_auth": False,
        },
        {
            "path_pattern": (
                r"/hls/init/(?P<camera_identifier>[A-Za-z0-9_]+)/"
                r"(?P<init_hash>[a-f0-9]{64}).mp4"
            ),
            "supported_methods": ["GET"],
            "method": "get_hls_init_file",
            "allow_token_parameter": True,
            "requires_auth": False,
        },
        {
            "path_pattern": (
                r"/hls/init/(?P<camera_identifier>[A-Za-z0-9_]+)/"
                r"(?P<tier_id>[0-9]+).mp4"
            ),
            "supported_methods": ["GET"],
            "method": "get_legacy_hls_init_file",
            "allow_token_parameter": True,
            "requires_auth": False,
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
        )
        if not playlist:
            LOGGER.warning(
                "Returning 404 for HLS playlist "
                "(camera=%s, recording_id=%s)",
                camera_identifier,
                recording_id,
            )
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
        )
        if not playlist:
            LOGGER.warning(
                "Returning 404 for HLS time-period playlist "
                "(camera=%s, start_timestamp=%s, end_timestamp=%s, date=%s)",
                camera_identifier,
                self.request_arguments["start_timestamp"],
                self.request_arguments["end_timestamp"],
                self.request_arguments["date"],
            )
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

    async def get_hls_segment(self, file_id: str):
        """Get a HLS media segment by file id."""
        request_started = time.perf_counter()
        resolve_started = request_started
        resolved_file = await self.run_in_executor(
            resolve_file_id,
            self._get_session,
            self._storage,
            int(file_id),
            HLS_SEGMENT_FILE_TYPES,
        )
        resolve_finished = time.perf_counter()
        if resolved_file is None:
            LOGGER.warning(
                "Returning 404 for unresolved HLS segment file id %s", file_id
            )
            self.response_error(HTTPStatus.NOT_FOUND, reason="Segment not found")
            return

        auth_started = resolve_finished
        if not await authorize_file_request(
            self, resolved_file.camera_identifier, failed=True
        ):
            return
        auth_finished = time.perf_counter()

        serve_started = auth_finished
        await serve_resolved_file(
            self,
            resolved_file,
            cache_control="public, max-age=31536000, immutable",
        )
        serve_finished = time.perf_counter()
        total_time = serve_finished - request_started
        if total_time >= HLS_SEGMENT_RESPONSE_WARN_SECONDS:
            LOGGER.warning(
                "Slow HLS segment response "
                "(file_id=%s, camera=%s, size=%s, total_ms=%.1f, "
                "resolve_ms=%.1f, auth_ms=%.1f, serve_ms=%.1f, path=%s)",
                file_id,
                resolved_file.camera_identifier,
                resolved_file.size,
                total_time * 1000,
                (resolve_finished - resolve_started) * 1000,
                (auth_finished - auth_started) * 1000,
                (serve_finished - serve_started) * 1000,
                resolved_file.path,
            )

    async def get_hls_init_file(self, camera_identifier: str, init_hash: str):
        """Get a hash-addressed HLS init file for a camera."""
        if not await authorize_file_request(self, camera_identifier, failed=True):
            return

        camera = self._get_camera(camera_identifier, failed=True)
        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        if not HLS_INIT_HASH_PATTERN.match(init_hash):
            self.response_error(HTTPStatus.BAD_REQUEST, reason="Invalid init hash")
            return

        init_file = await self.run_in_executor(
            _get_hashed_init_file,
            self._get_session,
            camera_identifier,
            init_hash,
        )
        if init_file is None:
            LOGGER.warning(
                "Returning 404 for missing HLS init file "
                "(camera=%s, init_hash=%s)",
                camera_identifier,
                init_hash,
            )
            self.response_error(HTTPStatus.NOT_FOUND, reason="Init file not found")
            return

        await serve_resolved_file(
            self,
            init_file,
            cache_control="public, max-age=31536000, immutable",
        )

    async def get_legacy_hls_init_file(self, camera_identifier: str, tier_id: str):
        """Get a legacy HLS init file by camera and tier id."""
        if not await authorize_file_request(self, camera_identifier, failed=True):
            return

        camera = self._get_camera(camera_identifier, failed=True)
        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        init_file = await self.run_in_executor(
            _get_init_file,
            camera,
            int(tier_id),
        )
        if init_file is None:
            LOGGER.warning(
                "Returning 404 for missing HLS init file "
                "(camera=%s, tier_id=%s)",
                camera_identifier,
                tier_id,
            )
            self.response_error(HTTPStatus.NOT_FOUND, reason="Init file not found")
            return

        await serve_resolved_file(
            self,
            init_file,
            cache_control="public, max-age=31536000, immutable",
        )


def _get_hashed_init_file(
    get_session: Callable[[], Session],
    camera_identifier: str,
    init_hash: str,
) -> ResolvedFile | None:
    """Get a hash-addressed HLS init sidecar referenced by available segments."""
    init_filename = f"init-{init_hash}.mp4"
    with get_session() as session:
        stmt = (
            select(FileLocations.path)
            .join(Files, Files.id == FileLocations.file_id)
            .where(Files.camera_identifier == camera_identifier)
            .where(Files.category == TIER_CATEGORY_RECORDER)
            .where(Files.subcategory == TIER_SUBCATEGORY_SEGMENTS)
            .where(Files.hls_init_hash == init_hash)
            .where(FileLocations.state == FileLocationState.AVAILABLE.value)
            .order_by(FileLocations.tier_id.asc())
        )
        segment_paths = session.execute(stmt).scalars().all()

    for segment_path in segment_paths:
        init_path = os.path.join(os.path.dirname(segment_path), init_filename)
        if os.path.isfile(init_path):
            return ResolvedFile(
                file_id=0,
                camera_identifier=camera_identifier,
                category=TIER_CATEGORY_RECORDER,
                subcategory=TIER_SUBCATEGORY_SEGMENTS,
                path=init_path,
                size=os.path.getsize(init_path),
            )
    return None


def _get_init_file(
    camera: AbstractCamera | FailedCamera,
    tier_id: int,
) -> ResolvedFile | None:
    """Get the init file for a camera tier."""
    try:
        tier_path = camera.tier_base_path(
            tier_id,
            TIER_CATEGORY_RECORDER,
            TIER_SUBCATEGORY_SEGMENTS,
        )
    except ValueError:
        return None

    init_path = os.path.normpath(
        os.path.join(get_segments_path({CONFIG_PATH: tier_path}, camera), "init.mp4")
    )
    if not os.path.isfile(init_path):
        LOGGER.error("Could not find init.mp4 file for camera %s", camera.identifier)
        return None

    return ResolvedFile(
        file_id=0,
        camera_identifier=camera.identifier,
        category=TIER_CATEGORY_RECORDER,
        subcategory=TIER_SUBCATEGORY_SEGMENTS,
        path=init_path,
        size=os.path.getsize(init_path),
    )


def _legacy_init_file_url(
    camera: AbstractCamera | FailedCamera,
    subpath: str,
    tier_id: int,
) -> str:
    """Return logical legacy HLS init file URL."""
    return f"{subpath}/api/v1/hls/init/{camera.identifier}/{tier_id}.mp4"


def _hashed_init_file_url(
    camera: AbstractCamera | FailedCamera,
    subpath: str,
    init_hash: str,
) -> str:
    """Return logical hash-addressed HLS init file URL."""
    return f"{subpath}/api/v1/hls/init/{camera.identifier}/{init_hash}.mp4"


def _init_file_url(
    camera: AbstractCamera | FailedCamera,
    subpath: str,
    files: list,
) -> str | None:
    """Return logical HLS init file URL for the first fragment."""
    if not files:
        return None
    if getattr(files[0], "hls_init_hash", None):
        return _hashed_init_file_url(camera, subpath, files[0].hls_init_hash)
    return _legacy_init_file_url(camera, subpath, files[0].tier_id)


def _legacy_init_files_available(
    camera: AbstractCamera | FailedCamera,
    files: list,
) -> bool:
    """Return if all legacy fragments have an available init.mp4."""
    legacy_tier_ids = {
        file.tier_id for file in files if not getattr(file, "hls_init_hash", None)
    }
    return all(_get_init_file(camera, tier_id) for tier_id in legacy_tier_ids)


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
) -> HlsClient:
    """Keep track of HLS client media and discontinuity sequences."""
    media_sequence = 0
    hls_client = HlsAPIHandler.hls_client_ids.get(hls_client_id, None)
    if hls_client:
        media_sequence = hls_client.media_sequence
        discontinuity_sequence = hls_client.discontinuity_sequence
        media_sequence += count_files_removed(hls_client.fragments, fragments)
        discontinuity_sequence += count_discontinuities_removed(
            hls_client.fragments, fragments
        )
        hls_client.fragments = fragments
        hls_client.media_sequence = media_sequence
        hls_client.discontinuity_sequence = discontinuity_sequence
    else:
        hls_client = HlsClient(
            client_id=hls_client_id,
            fragments=fragments,
            media_sequence=media_sequence,
            discontinuity_sequence=0,
            target_duration=get_target_duration(fragments),
        )
        HlsAPIHandler.hls_client_ids[hls_client_id] = hls_client
    return hls_client


def adjust_fragment_paths(
    _camera: AbstractCamera | FailedCamera, subpath: str, files: list
) -> list[Fragment]:
    """Adjust fragment paths to stable logical HLS segment URLs."""
    fragments = []
    for file in files:
        init_file = (
            _hashed_init_file_url(_camera, subpath, file.hls_init_hash)
            if getattr(file, "hls_init_hash", None)
            else _legacy_init_file_url(_camera, subpath, file.tier_id)
        )
        fragments.append(
            Fragment(
                file.filename,
                f"{subpath}/api/v1/hls/segments/{file.id}.m4s",
                file.duration,
                file.orig_ctime,
                init_file,
            )
        )
    return fragments


def _generate_playlist(
    get_session: Callable[[], Session],
    hls_client_id: str | None,
    camera: AbstractCamera | FailedCamera,
    recording_id: int,
    subpath: str,
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
    fragments = adjust_fragment_paths(camera, subpath, files)

    if not fragments:
        return None

    hls_client = update_hls_client(hls_client_id, fragments) if hls_client_id else None
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

    if not _legacy_init_files_available(camera, files):
        return None

    init_file_url = _init_file_url(camera, subpath, files)
    if not init_file_url:
        return None

    playlist = generate_playlist(
        fragments,
        init_file_url,
        media_sequence=hls_client.media_sequence if hls_client else 0,
        discontinuity_sequence=(
            hls_client.discontinuity_sequence if hls_client else 0
        ),
        target_duration=hls_client.target_duration if hls_client else None,
        end=end,
        file_directive=False,
    )
    return playlist


def _generate_playlist_time_period(
    get_session: Callable[[], Session],
    camera: AbstractCamera | FailedCamera,
    hls_client_id: str | None,
    utc_offset: datetime.timedelta,
    start_timestamp: int,
    end_timestamp: int | None = None,
    date: str | None = None,
    subpath: str = "",
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
    fragments = adjust_fragment_paths(camera, subpath, files)

    if not fragments:
        return None

    hls_client = update_hls_client(hls_client_id, fragments) if hls_client_id else None

    if not _legacy_init_files_available(camera, files):
        return None

    init_file_url = _init_file_url(camera, subpath, files)
    if not init_file_url:
        return None

    playlist = generate_playlist(
        fragments,
        init_file_url,
        media_sequence=hls_client.media_sequence if hls_client else 0,
        discontinuity_sequence=(
            hls_client.discontinuity_sequence if hls_client else 0
        ),
        target_duration=hls_client.target_duration if hls_client else None,
        end=end_playlist,
        file_directive=False,
    )
    return playlist
