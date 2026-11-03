"""Storage component utility functions."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from viseron.components.storage.const import (
    TIER_CATEGORY_SNAPSHOTS,
    TIER_SUBCATEGORY_EVENT_CLIPS,
    TIER_SUBCATEGORY_SEGMENTS,
    TIER_SUBCATEGORY_THUMBNAILS,
    TIER_SUBCATEGORY_TIMELAPSE,
)
from viseron.events import EventData

if TYPE_CHECKING:
    from types import TracebackType

    from viseron.components.storage.config import Tier
    from viseron.domains.camera import AbstractCamera, FailedCamera
    from viseron.viseron_types import SnapshotDomain


def get_segments_path(tier: Tier, camera: AbstractCamera | FailedCamera) -> str:
    """Get segments path for camera."""
    return os.path.join(tier.path, TIER_SUBCATEGORY_SEGMENTS, camera.identifier)


def get_event_clips_path(tier: Tier, camera: AbstractCamera | FailedCamera) -> str:
    """Get event clips path for camera."""
    return os.path.join(tier.path, TIER_SUBCATEGORY_EVENT_CLIPS, camera.identifier)


def get_thumbnails_path(tier: Tier, camera: AbstractCamera | FailedCamera) -> str:
    """Get thumbnails path for camera."""
    return os.path.join(tier.path, TIER_SUBCATEGORY_THUMBNAILS, camera.identifier)


def get_snapshots_path(
    tier: Tier,
    camera: AbstractCamera | FailedCamera,
    domain: SnapshotDomain,
) -> str:
    """Get snapshots path for camera."""
    return os.path.join(
        tier.path, TIER_CATEGORY_SNAPSHOTS, domain.value, camera.identifier
    )


def get_timelapse_path(tier: Tier, camera: AbstractCamera | FailedCamera) -> str:
    """Get timelapse path for camera."""
    return os.path.join(tier.path, TIER_SUBCATEGORY_TIMELAPSE, camera.identifier)


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

    def __enter__(self) -> int:
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
