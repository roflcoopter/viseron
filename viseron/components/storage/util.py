"""Storage component utility functions."""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import timedelta
from types import TracebackType
from typing import TYPE_CHECKING, Any

from viseron.components.storage.const import (
    CONFIG_DAYS,
    CONFIG_GB,
    CONFIG_HOURS,
    CONFIG_MB,
    CONFIG_MINUTES,
    CONFIG_PATH,
    TIER_CATEGORY_SNAPSHOTS,
    TIER_SUBCATEGORY_EVENT_CLIPS,
    TIER_SUBCATEGORY_SEGMENTS,
    TIER_SUBCATEGORY_THUMBNAILS,
)
from viseron.events import EventData
from viseron.types import SnapshotDomain

if TYPE_CHECKING:
    from viseron.domains.camera import AbstractCamera, FailedCamera


def calculate_age(age: dict[str, Any]) -> timedelta:
    """Calculate age in seconds."""
    if not age:
        return timedelta(seconds=0)

    return timedelta(
        days=age[CONFIG_DAYS] if age[CONFIG_DAYS] else 0,
        hours=age[CONFIG_HOURS] if age[CONFIG_HOURS] else 0,
        minutes=age[CONFIG_MINUTES] if age[CONFIG_MINUTES] else 0,
    )


def calculate_bytes(size: dict[str, Any]) -> int:
    """Calculate size in bytes."""
    max_bytes = 0
    if size[CONFIG_MB]:
        max_bytes += convert_mb_to_bytes(size[CONFIG_MB])
    if size[CONFIG_GB]:
        max_bytes += convert_gb_to_bytes(size[CONFIG_GB])
    return max_bytes


def convert_mb_to_bytes(mb: int) -> int:
    """Convert mb to bytes."""
    return mb * 1024 * 1024


def convert_gb_to_bytes(gb: int) -> int:
    """Convert gb to bytes."""
    return gb * 1024 * 1024 * 1024


def get_segments_path(
    tier: dict[str, Any], camera: AbstractCamera | FailedCamera
) -> str:
    """Get segments path for camera."""
    return os.path.join(tier[CONFIG_PATH], TIER_SUBCATEGORY_SEGMENTS, camera.identifier)


def get_event_clips_path(
    tier: dict[str, Any], camera: AbstractCamera | FailedCamera
) -> str:
    """Get event clips path for camera."""
    return os.path.join(
        tier[CONFIG_PATH], TIER_SUBCATEGORY_EVENT_CLIPS, camera.identifier
    )


def get_thumbnails_path(
    tier: dict[str, Any], camera: AbstractCamera | FailedCamera
) -> str:
    """Get thumbnails path for camera."""
    return os.path.join(
        tier[CONFIG_PATH], TIER_SUBCATEGORY_THUMBNAILS, camera.identifier
    )


def get_snapshots_path(
    tier: dict[str, Any],
    camera: AbstractCamera | FailedCamera,
    domain: SnapshotDomain,
) -> str:
    """Get snapshots path for camera."""
    return os.path.join(
        tier[CONFIG_PATH], TIER_CATEGORY_SNAPSHOTS, domain.value, camera.identifier
    )


@dataclass
class EventFile(EventData):
    """Event data for file events."""

    camera_identifier: str
    category: str
    subcategory: str
    file_name: str
    path: str


class EventFileCreated(EventFile):
    """Event data for file created events."""


class EventFileDeleted(EventFile):
    """Event data for file deleted events."""


class RequestedFilesCount:
    """Context manager for keeping track of recently requested files."""

    def __init__(self) -> None:
        self.count = 0
        self.filenames: list[str] = []

    def remove_filename(self, filename: str) -> None:
        """Remove a filename from the list of active filenames."""
        self.filenames.remove(filename)

    def __call__(self, filename: str) -> RequestedFilesCount:
        """Add a filename to the list of active filenames."""
        self.filenames.append(filename)
        timer = threading.Timer(2, self.remove_filename, args=(filename,))
        timer.start()
        return self

    def __enter__(self):
        """Increment the counter when entering the context."""
        self.count += 1
        return self.count

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Decrement the counter when exiting the context."""
        self.count -= 1
