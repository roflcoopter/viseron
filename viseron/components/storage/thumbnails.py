"""Helpers for recording thumbnail recovery."""

from __future__ import annotations

import logging
import os
import subprocess as sp
from dataclasses import dataclass
from time import sleep
from typing import TYPE_CHECKING

from sqlalchemy import update

from viseron.components.storage.const import (
    TIER_CATEGORY_RECORDER,
    TIER_SUBCATEGORY_THUMBNAILS,
)
from viseron.components.storage.files import upsert_file
from viseron.components.storage.models import Recordings
from viseron.components.storage.queries import get_recording_fragments
from viseron.components.storage.util import fsync_directory, get_storage_temp_path
from viseron.const import CAMERA_SEGMENT_DURATION
from viseron.domains.camera.fragmenter import Fragment, generate_playlist
from viseron.helpers import create_directory

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

    from viseron.components.storage import Storage
    from viseron.domains.camera import AbstractCamera, FailedCamera

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecoveredThumbnail:
    """A recovered recording thumbnail."""

    path: str
    file_id: int


def upsert_thumbnail_file(
    get_session: Callable[[], Session],
    storage: Storage,
    camera_identifier: str,
    thumbnail_path: str,
) -> int | None:
    """Ensure a generated thumbnail has a Files row and return its id."""
    return upsert_file(
        get_session,
        storage,
        camera_identifier,
        TIER_CATEGORY_RECORDER,
        TIER_SUBCATEGORY_THUMBNAILS,
        thumbnail_path,
    )


def _set_recording_thumbnail_path(
    get_session: Callable[[], Session],
    recording_id: int,
    thumbnail_path: str,
    thumbnail_file_id: int | None = None,
) -> None:
    """Persist a recording thumbnail path and optional Files reference."""
    values: dict[str, str | int | None] = {"thumbnail_path": thumbnail_path}
    if thumbnail_file_id is not None:
        values["thumbnail_file_id"] = thumbnail_file_id

    with get_session() as session:
        stmt = (
            update(Recordings)
            .where(Recordings.id == recording_id)
            .values(**values)
        )
        session.execute(stmt)
        session.commit()


def _extract_thumbnail_from_fragment(
    camera: AbstractCamera | FailedCamera,
    fragment: Fragment,
    thumbnail_path: str,
) -> bool:
    """Extract a thumbnail from a fragment."""
    init_file = os.path.join(os.path.dirname(fragment.path), "init.mp4")
    if not os.path.exists(init_file):
        init_file = os.path.join(camera.segments_folder, "init.mp4")
    if not os.path.exists(init_file):
        LOGGER.debug("No init.mp4 found for thumbnail repair")
        return False

    create_directory(os.path.dirname(thumbnail_path))
    temp_path = f"{get_storage_temp_path(thumbnail_path)}.jpg"
    playlist = generate_playlist(
        [fragment],
        init_file,
        end=True,
        file_directive=True,
    )
    try:
        result = sp.run(  # type: ignore[call-overload]
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "hls",
                "-protocol_whitelist",
                "file,pipe,fd",
                "-i",
                "-",
                "-frames:v",
                "1",
                "-q:v",
                "2",
                "-y",
                temp_path,
            ],
            input=playlist.encode("utf-8"),
            capture_output=True,
            check=True,
            timeout=30,
        )
        if result.stderr:
            LOGGER.debug(
                "Thumbnail repair ffmpeg output: %s",
                result.stderr.decode("utf-8", errors="replace"),
            )
        if os.path.getsize(temp_path) <= 0:
            LOGGER.debug("Thumbnail repair produced an empty file")
            return False
        os.replace(temp_path, thumbnail_path)
        fsync_directory(os.path.dirname(thumbnail_path))
    except (sp.CalledProcessError, sp.TimeoutExpired, OSError) as error:
        LOGGER.debug(
            "Failed extracting thumbnail from fragment %s",
            fragment.path,
            exc_info=error,
        )
        return False
    finally:
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass
    return True


def recover_recording_thumbnail(
    storage: Storage,
    camera: AbstractCamera | FailedCamera,
    recording_id: int,
    thumbnail_path: str | None,
    lookback: float,
    *,
    wait_for_segments: bool = False,
) -> RecoveredThumbnail | None:
    """Recover or register a recording thumbnail and return its Files id."""
    if wait_for_segments:
        sleep(CAMERA_SEGMENT_DURATION * 2)

    target_path = thumbnail_path or os.path.join(
        camera.thumbnails_folder, f"{recording_id}.jpg"
    )
    target_path = os.path.normpath(target_path)
    if os.path.exists(target_path):
        file_id = upsert_thumbnail_file(
            storage.get_session, storage, camera.identifier, target_path
        )
        if file_id is None:
            return None
        _set_recording_thumbnail_path(
            storage.get_session, recording_id, target_path, file_id
        )
        return RecoveredThumbnail(path=target_path, file_id=file_id)

    files = get_recording_fragments(recording_id, lookback, storage.get_session)
    fragments = [
        Fragment(file.filename, file.path, file.duration, file.orig_ctime)
        for file in files
    ]
    for fragment in fragments:
        if _extract_thumbnail_from_fragment(camera, fragment, target_path):
            file_id = upsert_thumbnail_file(
                storage.get_session, storage, camera.identifier, target_path
            )
            if file_id is None:
                return None
            _set_recording_thumbnail_path(
                storage.get_session, recording_id, target_path, file_id
            )
            return RecoveredThumbnail(path=target_path, file_id=file_id)

    LOGGER.error(
        "Failed to repair thumbnail for recording %s: no usable fragments",
        recording_id,
    )
    return None
