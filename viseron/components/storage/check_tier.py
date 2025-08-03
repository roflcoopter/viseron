"""Tier size/age checker for the storage component."""

from __future__ import annotations

import datetime
import logging
import os
import shutil
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import scoped_session, sessionmaker

from viseron.components.storage.const import ENGINE
from viseron.components.storage.models import Files, Recordings
from viseron.const import CAMERA_SEGMENT_DURATION
from viseron.helpers import utcnow

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from viseron.components.storage.storage_subprocess import (
        DataItem,
        DataItemDeleteFile,
        DataItemMoveFile,
    )

LOGGER = logging.getLogger(__name__)

FILES_DTYPE = np.dtype(
    [
        ("id", np.int64),
        ("size", np.int64),
        ("orig_ctime", np.int64),
        ("path", "U512"),
        ("tier_path", "U512"),
    ]
)

RECORDINGS_DTYPE = np.dtype(
    [
        ("id", np.int64),
        ("start_time", np.int64),
        ("adjusted_start_time", np.int64),
        ("end_time", np.int64),
        ("created_at", np.int64),
    ]
)

RECORDINGS_FILES_DTYPE = np.dtype(
    [
        ("recording_id", np.int64),
        ("id", np.int64),
        ("size", np.int64),
        ("orig_ctime", np.int64),
        ("path", "U512"),
        ("tier_path", "U512"),
    ]
)


class Worker:
    """Worker process for checking storage tiers in a separate shell."""

    def __init__(
        self,
    ) -> None:
        self._get_session: Callable[[], Session] = scoped_session(
            sessionmaker(bind=ENGINE)
        )
        self._last_call: dict[str, float] = {}
        self._check_locks: dict[str, threading.Lock] = {}
        self._checks_in_progress: dict[str, bool] = {}

    def _check_tier(self, item: DataItem) -> None:
        if item.cmd == "check_tier" and item.files_enabled:
            LOGGER.debug(
                "Received check_tier command for files "
                "for %s tier %s category %s subcategory %s",
                item.camera_identifier,
                item.tier_id,
                item.category,
                item.subcategories[0],
            )
            files = self.check_tier_files(item)

        if item.cmd == "check_tier" and item.events_enabled:
            LOGGER.debug(
                "Received check_tier command for recordings "
                "for %s tier %s category %s subcategory %s",
                item.camera_identifier,
                item.tier_id,
                item.category,
                item.subcategories[0],
            )
            recordings = self.check_tier_recordings(item)

        if item.events_enabled and not item.files_enabled:
            item.data = recordings
        elif item.files_enabled and not item.events_enabled:
            item.data = files
        elif item.events_enabled and item.files_enabled:
            LOGGER.debug(
                "Finding overlapping files and recordings "
                "for %s tier %s category %s subcategory %s",
                item.camera_identifier,
                item.tier_id,
                item.category,
                item.subcategories[0],
            )
            # Find overlapping IDs
            if files.size > 0 and recordings.size > 0:
                overlapping_ids = np.intersect1d(files["id"], recordings["id"])
                if overlapping_ids.size > 0:
                    # Return full recordings array for overlapping IDs
                    item.data = recordings[np.isin(recordings["id"], overlapping_ids)]
                else:
                    item.data = np.empty(0, dtype=recordings.dtype)
            else:
                item.data = np.empty(
                    0,
                    dtype=recordings.dtype if recordings.size > 0 else files.dtype,
                )
        else:
            item.data = np.empty(0, dtype=FILES_DTYPE)

        LOGGER.debug(
            "Found %d files to move for %s tier %s category %s subcategory %s",
            len(item.data) if item.data is not None else 0,
            item.camera_identifier,
            item.tier_id,
            item.category,
            item.subcategories[0],
        )

    def check_tier(self, item: DataItem) -> None:
        """Handle input commands in the child process.

        Calls are throttled based on the throttle_period defined in the tier.
        """
        if item.camera_identifier not in self._check_locks:
            self._check_locks[item.camera_identifier] = threading.Lock()
        if item.throttle_key not in self._last_call:
            self._last_call[item.throttle_key] = 0
        if item.camera_identifier not in self._checks_in_progress:
            self._checks_in_progress[item.camera_identifier] = False

        with self._check_locks[item.camera_identifier]:
            if self._checks_in_progress[item.camera_identifier]:
                return
            now = utcnow().timestamp()
            throttle_period = item.throttle_period.total_seconds()
            last_call = self._last_call[item.throttle_key]
            if throttle_period > 0 and (now - last_call) < throttle_period:
                item.data = None
                return
            self._checks_in_progress[item.camera_identifier] = True

        try:
            self._check_tier(item)
        finally:
            LOGGER.debug(
                "Execution took %.2f seconds for %s tier %s category %s subcategory %s",
                utcnow().timestamp() - now,
                item.camera_identifier,
                item.tier_id,
                item.category,
                item.subcategories[0],
            )
            with self._check_locks[item.camera_identifier]:
                self._last_call[item.throttle_key] = utcnow().timestamp()
                self._checks_in_progress[item.camera_identifier] = False

    def move_file(self, item: DataItemMoveFile) -> None:
        """Move file from source to destination."""
        move_file(
            self._get_session,
            item.src,
            item.dst,
            LOGGER,
        )

    def delete_file(self, item: DataItemDeleteFile) -> None:
        """Delete file."""
        delete_file(
            self._get_session,
            item.src,
            LOGGER,
        )

    def work_input(self, item: DataItem | DataItemMoveFile | DataItemDeleteFile):
        """Perform work on input item from child process."""
        try:
            if item.cmd == "check_tier":
                self.check_tier(item)
            if item.cmd == "move_file":
                self.move_file(item)
            if item.cmd == "delete_file":
                self.delete_file(item)
        except Exception as e:  # pylint: disable=broad-except
            LOGGER.error(
                "Error processing command: %s, error: %s",
                item,
                e,
            )
            item.error = str(e)

    def load_tier(self, item: DataItem):
        """Load the tier data for the camera."""
        data = load_tier(
            self._get_session,
            item.category,
            item.subcategories,
            item.tier_id,
            item.camera_identifier,
        )
        LOGGER.debug(
            "Loaded %d files into numpy array",
            len(data),
        )
        return data

    def load_recordings(self, item: DataItem):
        """Load the recordings data for the camera."""
        data = load_recordings(
            self._get_session,
            item.camera_identifier,
        )
        LOGGER.debug(
            "Loaded %d recordings into numpy array",
            len(data),
        )
        return data

    def check_tier_files(self, item: DataItem):
        """Check the tier using the loaded numpy array."""
        data = self.load_tier(item)
        now = utcnow()

        # If min_age is not set, we want to ignore recent files.
        # This is to avoid moving files that are still being written to
        if item.min_age:
            min_age_timestamp = (now - item.min_age).timestamp()
        else:
            min_age_timestamp = (
                now - datetime.timedelta(seconds=CAMERA_SEGMENT_DURATION * 2)
            ).timestamp()

        if item.max_age:
            max_age_timestamp = (now - item.max_age).timestamp()
        else:
            max_age_timestamp = 0

        LOGGER.debug(
            "Files to move parameters: "
            "camera_identifier(%s), tier_id(%s), category(%s), subcategories(%s), "
            "max_bytes(%s), min_age_timestamp(%s), min_bytes(%s), "
            "max_age_timestamp(%s)",
            item.camera_identifier,
            item.tier_id,
            item.category,
            item.subcategories,
            item.max_bytes,
            min_age_timestamp,
            item.min_bytes,
            max_age_timestamp,
        )

        rows_to_move = get_files_to_move(
            data,
            item.max_bytes,
            min_age_timestamp,
            item.min_bytes,
            max_age_timestamp,
        )

        return rows_to_move

    def check_tier_recordings(
        self,
        item: DataItem,
        now: datetime.datetime | None = None,
    ):
        """Check the recordings tier using the loaded numpy array."""
        if (
            item.events_max_bytes is None
            or item.events_min_bytes is None
            or item.events_min_age is None
            or item.events_max_age is None
        ):
            raise ValueError(
                "events_max_bytes, events_min_bytes, events_min_age, and events_max_age"
                " must be set for check_tier_recordings"
            )

        if now is None:
            now = utcnow()

        files_data = self.load_tier(item)
        recordings_data = self.load_recordings(item)
        now = utcnow()

        # If min_age is not set, we want to ignore files that are less than 5 secs old
        # This is to avoid moving files that are still being written to
        if item.events_min_age:
            min_age_timestamp = (now - item.events_min_age).timestamp()
        else:
            min_age_timestamp = (
                now - datetime.timedelta(seconds=CAMERA_SEGMENT_DURATION * 2)
            ).timestamp()

        if item.events_max_age:
            max_age_timestamp = (now - item.events_max_age).timestamp()
        else:
            max_age_timestamp = 0

        # We want to ignore files that are less than 5 times the
        # segment duration old. This is to improve HLS streaming
        file_min_age = (
            now - datetime.timedelta(seconds=CAMERA_SEGMENT_DURATION * 5)
        ).timestamp()

        LOGGER.debug(
            "Recordings to move parameters: "
            "camera_identifier(%s), tier_id(%s), category(%s), subcategories(%s), "
            "events_max_bytes(%s), min_age_timestamp(%s), events_min_bytes(%s), "
            "max_age_timestamp(%s), file_min_age(%s)",
            item.camera_identifier,
            item.tier_id,
            item.category,
            item.subcategories,
            item.events_max_bytes,
            min_age_timestamp,
            item.events_min_bytes,
            max_age_timestamp,
            file_min_age,
        )
        rows_to_move = get_recordings_to_move(
            recordings_data,
            files_data,
            CAMERA_SEGMENT_DURATION,
            item.events_max_bytes,
            min_age_timestamp,
            item.events_min_bytes,
            max_age_timestamp,
            file_min_age,
        )

        return rows_to_move


def load_tier(
    get_session: Callable[..., Session],
    category: str,
    subcategories: list[str],
    tier_id: int,
    camera_identifier: str,
):
    """Load the tier files data for the camera."""
    with get_session() as session:
        stmt = select(
            Files.id, Files.size, Files.orig_ctime, Files.path, Files.tier_path
        ).where(
            Files.camera_identifier == camera_identifier,
            Files.tier_id == tier_id,
            Files.category == category,
            Files.subcategory.in_(subcategories),
        )
        result = session.execute(stmt).yield_per(1000)
        data = [
            (
                row.id,
                row.size,
                int(row.orig_ctime.timestamp()),
                row.path,
                row.tier_path,
            )
            for row in result
        ]
        return np.array(
            data,
            dtype=FILES_DTYPE,
        )


def load_recordings(
    get_session: Callable[..., Session],
    camera_identifier: str,
):
    """Load the tier recordings data for the camera."""
    with get_session() as session:
        stmt = select(
            Recordings.id,
            Recordings.start_time,
            Recordings.end_time,
            Recordings.adjusted_start_time,
            Recordings.created_at,
        ).where(
            Recordings.camera_identifier == camera_identifier,
        )
        result = session.execute(stmt).yield_per(1000)
        data = [
            (
                row.id,
                int(row.start_time.timestamp()),
                int(row.adjusted_start_time.timestamp()),
                int(row.end_time.timestamp() if row.end_time else utcnow().timestamp()),
                int(row.created_at.timestamp()),
            )
            for row in result
        ]

    return np.array(
        data,
        dtype=RECORDINGS_DTYPE,
    )


def get_files_to_move(
    data: np.ndarray,
    max_bytes: int,
    min_age_timestamp: float,
    min_bytes: int,
    max_age_timestamp: float,
):
    """Get id of files to move.

    The processing is done in the following steps:
    1. First the array is sorted by the timestamp.
    2. np.cumsum is used to calculate the cumulative sum of the sizes.
    3. Any rows where the cumulative size exceeds the tier size are marked
        for moving to the next tier.
    """
    # Sort by timestamp
    sorted_indices = np.argsort(data["orig_ctime"])
    data = data[sorted_indices][::-1]

    # Calculate cumulative size
    cumulative_size = np.cumsum(data["size"])

    # Find indices where cumulative size exceeds the tier size
    bytes_indices_to_move = np.empty(0, dtype=np.int64)
    if max_bytes > 0:
        bytes_indices_to_move = np.where(
            (cumulative_size >= max_bytes) & (data["orig_ctime"] <= min_age_timestamp)
        )[0]

    age_indices_to_move = np.empty(0, dtype=np.int64)
    if max_age_timestamp > 0:
        age_indices_to_move = np.where(
            (data["orig_ctime"] < max_age_timestamp) & (cumulative_size >= min_bytes)
        )[0]

    # Combine the indices to move based on size and age
    indices_to_move = np.unique(
        np.concatenate((bytes_indices_to_move, age_indices_to_move))
    )

    if indices_to_move.size > 0:
        rows_to_move = data[indices_to_move]
        stripped_rows = rows_to_move[["id", "path", "tier_path"]]
        return stripped_rows[::-1]

    return np.empty(0, dtype=data.dtype)


def get_recordings_to_move(
    recordings_data: np.ndarray,
    files_data: np.ndarray,
    segment_length: int,
    max_bytes: int,
    min_age_timestamp: float,
    min_bytes: int,
    max_age_timestamp: float,
    file_min_age_timestamp: float,
):
    """Get files to move based on recording grouping."""
    # Sort recordings by adjusted start time (descending)
    sorted_indices_recordings = np.argsort(recordings_data["adjusted_start_time"])[::-1]
    recordings_data = recordings_data[sorted_indices_recordings]

    # Sort files_data by orig_ctime (ascending) for efficient searching
    files_data.sort(order="orig_ctime")

    recordings_size = np.zeros(len(recordings_data), dtype=np.int64)
    associated_files_data_list = []

    for i, recording in enumerate(recordings_data):
        if files_data.size > 0:
            start_time_search = recording["adjusted_start_time"]
            end_time_search = recording["end_time"] + segment_length

            # Find relevant files using searchsorted
            start_idx = np.searchsorted(
                files_data["orig_ctime"], start_time_search, side="left"
            )
            end_idx = np.searchsorted(
                files_data["orig_ctime"], end_time_search, side="right"
            )
            relevant_files_for_recording = files_data[start_idx:end_idx]
        else:
            relevant_files_for_recording = np.empty(0, dtype=files_data.dtype)

        current_recording_total_size = 0
        if relevant_files_for_recording.size > 0:
            for file_row in relevant_files_for_recording:
                associated_files_data_list.append(
                    (
                        recording["id"],
                        file_row["id"],
                        file_row["size"],
                        file_row["orig_ctime"],
                        file_row["path"],
                        file_row["tier_path"],
                    )
                )
                current_recording_total_size += file_row["size"]
        recordings_size[i] = current_recording_total_size

    associated_file_ids_set = {tup[1] for tup in associated_files_data_list}

    other_files_data_list = []
    if files_data.size > 0:
        for file_row in files_data:
            if file_row["id"] not in associated_file_ids_set:
                other_files_data_list.append(
                    (
                        -1,  # recording_id for unassociated files
                        file_row["id"],
                        file_row["size"],
                        file_row["orig_ctime"],
                        file_row["path"],
                        file_row["tier_path"],
                    )
                )

    combined_files_list = associated_files_data_list + other_files_data_list

    if not combined_files_list:
        return np.empty(0, dtype=RECORDINGS_FILES_DTYPE)

    recordings_files = np.array(combined_files_list, dtype=RECORDINGS_FILES_DTYPE)

    # Sort by id, then orig_ctime to ensure consistent unique selection if needed
    # Although file IDs should be unique.
    recordings_files.sort(order=["id", "orig_ctime"])

    recording_cumulative_sizes = np.cumsum(recordings_size)

    bytes_indices_to_move_recordings = np.empty(0, dtype=np.int64)
    if max_bytes > 0:
        bytes_indices_to_move_recordings = np.where(
            (recording_cumulative_sizes >= max_bytes)
            & (recordings_data["created_at"] <= min_age_timestamp)
        )[0]

    age_indices_to_move_recordings = np.empty(0, dtype=np.int64)
    if max_age_timestamp > 0:
        age_indices_to_move_recordings = np.where(
            (recordings_data["created_at"] < max_age_timestamp)
            & (recording_cumulative_sizes >= min_bytes)
        )[0]

    # Indices of recordings_data that need to be moved
    recording_indices_to_move = np.unique(
        np.concatenate(
            (bytes_indices_to_move_recordings, age_indices_to_move_recordings)
        )
    )

    files_to_move_list = []

    if recording_indices_to_move.size > 0:
        moved_recording_ids = recordings_data[recording_indices_to_move]["id"]
        # Select files associated with these moved recordings
        for r_file in recordings_files:
            if r_file["recording_id"] in moved_recording_ids:
                if r_file["orig_ctime"] <= file_min_age_timestamp:
                    files_to_move_list.append(r_file)
            elif r_file["recording_id"] == -1:  # Always consider "other" files
                if r_file["orig_ctime"] <= file_min_age_timestamp:
                    files_to_move_list.append(r_file)
    elif files_data.size > 0:  # No recordings to move, but check "other" files
        for r_file in recordings_files:
            if r_file["recording_id"] == -1:
                if r_file["orig_ctime"] <= file_min_age_timestamp:
                    files_to_move_list.append(r_file)

    if not files_to_move_list:
        return np.empty(0, dtype=RECORDINGS_FILES_DTYPE)

    # Convert list of structured array rows to a new array
    files_to_move_np = np.array(files_to_move_list, dtype=RECORDINGS_FILES_DTYPE)

    # Ensure unique files by ID, taking the first occurrence after sorting
    if files_to_move_np.size > 0:
        _, unique_indices = np.unique(files_to_move_np["id"], return_index=True)
        files_to_move_np = files_to_move_np[unique_indices]
    else:
        return np.empty(0, dtype=RECORDINGS_FILES_DTYPE)

    # Strip to required columns
    stripped_files_to_move = files_to_move_np[
        ["recording_id", "id", "path", "tier_path"]
    ]

    # Remove any files that are not m4s
    stripped_files_to_move = stripped_files_to_move[
        np.char.endswith(stripped_files_to_move["path"], ".m4s")
    ]
    return stripped_files_to_move


def delete_file(
    get_session: Callable[..., Session],
    path: str,
    logger: logging.Logger,
) -> None:
    """Delete file."""
    logger.debug("Deleting file %s", path)
    with get_session() as session:
        stmt = delete(Files).where(Files.path == path)
        session.execute(stmt)
        session.commit()

    try:
        os.remove(path)
    except FileNotFoundError as error:
        logger.debug(f"Failed to delete file {path}: {error}")
        raise error


def move_file(
    get_session: Callable[..., Session],
    src: str,
    dst: str,
    logger: logging.Logger,
) -> None:
    """Move file from src to dst.

    To avoid race conditions where a file is referenced at the same time as it is being
    moved, causing a 404 in the browser, we copy the file to the new location and then
    delete the old one.
    """
    logger.debug("Moving file from %s to %s", src, dst)
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(src, dst)
        os.remove(src)
    except FileNotFoundError as error:
        logger.debug(f"Failed to move file {src} to {dst}: {error}")
        with get_session() as session:
            stmt = delete(Files).where(Files.path == src)
            session.execute(stmt)
            session.commit()
        raise error
    except OSError as error:
        logger.debug(f"Failed to move file {src} to {dst}: {error}")
        with get_session() as session:
            stmt = delete(Files).where(Files.path == src)
            session.execute(stmt)
            session.commit()
        try:
            os.remove(src)
        except FileNotFoundError as _error:
            logger.debug(f"Failed to delete file {src}: {_error}")
        raise error
