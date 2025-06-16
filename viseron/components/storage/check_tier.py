"""Tier size/age checker for the storage component."""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import scoped_session, sessionmaker

from viseron.components.storage.const import ENGINE
from viseron.components.storage.models import Files, Recordings
from viseron.const import CAMERA_SEGMENT_DURATION
from viseron.helpers import utcnow

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from viseron.components.storage.storage_subprocess import DataItem


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

    def work_input(self, item: DataItem) -> None:
        """Handle input commands in the child process."""
        try:
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
                        item.data = recordings[
                            np.isin(recordings["id"], overlapping_ids)
                        ]
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

        except Exception as e:  # pylint: disable=broad-except
            LOGGER.error(
                "Error processing command: %s",
                e,
            )
            item.error = str(e)
            return

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
    # Sort recordings by adjusted start time
    if recordings_data.size == 0:
        return np.empty(0, dtype=RECORDINGS_FILES_DTYPE)

    sorted_indices = np.argsort(recordings_data["adjusted_start_time"])
    recordings_data = recordings_data[sorted_indices][::-1]

    # Calculate cumulative size of files for each recording
    recordings_size = np.zeros(len(recordings_data), dtype=np.int64)

    # Initialize a list to store arrays of files for each recording
    all_recording_files_list = []

    for i, recording in enumerate(recordings_data):
        # Filter files_data for the current recording
        mask = (files_data["orig_ctime"] >= recording["adjusted_start_time"]) & (
            files_data["orig_ctime"] <= recording["end_time"] + segment_length
        )
        relevant_files_for_recording = files_data[mask]

        if relevant_files_for_recording.size > 0:
            current_recording_files_np = np.empty(
                len(relevant_files_for_recording), dtype=RECORDINGS_FILES_DTYPE
            )
            current_recording_files_np["recording_id"] = recording["id"]
            current_recording_files_np["id"] = relevant_files_for_recording["id"]
            current_recording_files_np["size"] = relevant_files_for_recording["size"]
            current_recording_files_np["orig_ctime"] = relevant_files_for_recording[
                "orig_ctime"
            ]
            current_recording_files_np["path"] = relevant_files_for_recording["path"]
            current_recording_files_np["tier_path"] = relevant_files_for_recording[
                "tier_path"
            ]

            recordings_size[i] = np.sum(current_recording_files_np["size"])
            all_recording_files_list.append(current_recording_files_np)
        else:
            recordings_size[i] = 0

    if all_recording_files_list:
        associated_recording_files = np.concatenate(all_recording_files_list)
    else:
        associated_recording_files = np.empty(0, dtype=RECORDINGS_FILES_DTYPE)

    # Identify files from files_data not present in associated_recording_files
    if associated_recording_files.size > 0:
        associated_file_ids = associated_recording_files["id"]
        unassociated_mask = ~np.isin(files_data["id"], associated_file_ids)
    else:
        unassociated_mask = np.ones(len(files_data), dtype=bool)

    unassociated_files_subset = files_data[unassociated_mask]

    other_files_np = np.empty(0, dtype=RECORDINGS_FILES_DTYPE)
    if unassociated_files_subset.size > 0:
        other_files_np = np.empty(
            len(unassociated_files_subset), dtype=RECORDINGS_FILES_DTYPE
        )
        other_files_np["recording_id"] = -1
        other_files_np["id"] = unassociated_files_subset["id"]
        other_files_np["size"] = unassociated_files_subset["size"]
        other_files_np["orig_ctime"] = unassociated_files_subset["orig_ctime"]
        other_files_np["path"] = unassociated_files_subset["path"]
        other_files_np["tier_path"] = unassociated_files_subset["tier_path"]

    # Combine associated files and other files
    if associated_recording_files.size > 0 and other_files_np.size > 0:
        recordings_files = np.concatenate((associated_recording_files, other_files_np))
    elif associated_recording_files.size > 0:
        recordings_files = associated_recording_files
    elif other_files_np.size > 0:
        recordings_files = other_files_np
    else:
        recordings_files = np.empty(0, dtype=RECORDINGS_FILES_DTYPE)

    if recordings_files.size == 0:
        return np.empty(0, dtype=RECORDINGS_FILES_DTYPE)

    # Sort the recordings_files by id and then by orig_ctime
    recordings_files.sort(order=["id", "orig_ctime"])

    recording_cumulative_sizes = np.cumsum(recordings_size)

    bytes_indices_to_move = np.empty(0, dtype=np.int64)
    if max_bytes > 0:
        bytes_indices_to_move = np.where(
            (recording_cumulative_sizes >= max_bytes)
            & (recordings_data["created_at"] <= min_age_timestamp)
        )[0]

    age_indices_to_move = np.empty(0, dtype=np.int64)
    if max_age_timestamp > 0:
        age_indices_to_move = np.where(
            (recordings_data["created_at"] < max_age_timestamp)
            & (recording_cumulative_sizes >= min_bytes)
        )[0]

    indices_to_move = np.unique(
        np.concatenate((bytes_indices_to_move, age_indices_to_move))
    )

    files_to_move = np.empty(0, dtype=RECORDINGS_FILES_DTYPE)
    if indices_to_move.size > 0:
        moved_recording_ids = recordings_data[indices_to_move]["id"]
        mask_files_from_moved_recordings = np.isin(
            recordings_files["recording_id"], moved_recording_ids
        )
        mask_other_files = recordings_files["recording_id"] == -1
        files_to_move = recordings_files[
            mask_files_from_moved_recordings | mask_other_files
        ]
    elif np.any(recordings_files["recording_id"] == -1):
        files_to_move = recordings_files[recordings_files["recording_id"] == -1]

    if files_to_move.size > 0:
        _, unique_indices = np.unique(files_to_move["id"], return_index=True)
        files_to_move = files_to_move[unique_indices]
        indices_to_move = np.where(
            files_to_move["orig_ctime"] <= file_min_age_timestamp
        )[0]
        files_to_move = files_to_move[indices_to_move]

    stripped_files_to_move = files_to_move[["recording_id", "id", "path", "tier_path"]]
    return stripped_files_to_move
