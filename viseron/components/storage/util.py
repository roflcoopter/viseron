"""Storage component utility functions."""
from __future__ import annotations

import os
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from viseron.components.storage.const import (
    CONFIG_DAYS,
    CONFIG_GB,
    CONFIG_HOURS,
    CONFIG_MB,
    CONFIG_MINUTES,
    CONFIG_PATH,
)

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


def get_recorder_path(
    tier: dict[str, Any], camera: AbstractCamera | FailedCamera, subcategory: str
) -> str:
    """Get recorder path for camera."""
    return os.path.join(tier[CONFIG_PATH], subcategory, camera.identifier)


def get_thumbnails_path(
    tier: dict[str, Any], camera: AbstractCamera | FailedCamera
) -> str:
    """Get thumbnails path for camera."""
    return os.path.join(tier[CONFIG_PATH], "thumbnails", camera.identifier)


def get_snapshots_path(
    tier: dict[str, Any],
    camera: AbstractCamera | FailedCamera,
    domain: str,
) -> str:
    """Get snapshots path for camera."""
    return os.path.join(tier[CONFIG_PATH], "snapshots", domain, camera.identifier)


def files_to_move_overlap(events_file_ids, continuous_file_ids):
    """Find the files that are in both events and continuous delete list."""
    events_dict = {row.file_id: row for row in events_file_ids}
    continuous_dict = {row.id: row for row in continuous_file_ids}
    # Find the matching tuples based on "file_id" and "id"
    matched_ids = [
        events_dict[file_id] for file_id in events_dict if file_id in continuous_dict
    ]
    return matched_ids
