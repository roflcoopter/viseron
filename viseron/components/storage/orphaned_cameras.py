"""Find and delete stored data belonging to cameras that are no longer configured.

When a camera is removed from the configuration its recordings, snapshots and
database rows are left behind. The regular cleanup jobs cannot reclaim them
because every one of them only walks the paths of *registered* cameras, so the
data is invisible to them and stays on disk forever.

This module finds those leftovers and deletes them on request.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, select

from viseron.components.storage.const import (
    CONFIG_FACE_RECOGNITION,
    CONFIG_IMAGE_CLASSIFICATION,
    CONFIG_LICENSE_PLATE_RECOGNITION,
    CONFIG_MOTION_DETECTOR,
    CONFIG_OBJECT_DETECTOR,
    CONFIG_PATH,
    CONFIG_RECORDER,
    CONFIG_SNAPSHOTS,
    CONFIG_TIERS,
    CONFIG_TIMELAPSE,
    TIER_CATEGORY_SNAPSHOTS,
    TIER_SUBCATEGORY_EVENT_CLIPS,
    TIER_SUBCATEGORY_SEGMENTS,
    TIER_SUBCATEGORY_THUMBNAILS,
    TIER_SUBCATEGORY_TIMELAPSE,
)
from viseron.components.storage.models import (
    Files,
    Motion,
    MotionContours,
    Objects,
    PostProcessorResults,
    Recordings,
)
from viseron.const import FAILED, LOADING
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.viseron_types import SnapshotDomain

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from viseron import Viseron
    from viseron.components.storage import Storage

LOGGER = logging.getLogger(__name__)

# Camera identifiers are slugs, see viseron.helpers.validators.valid_camera_identifier
CAMERA_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

# Directories directly under a tier path that contain one folder per camera
CAMERA_SUBCATEGORY_DIRS = (
    TIER_SUBCATEGORY_SEGMENTS,
    TIER_SUBCATEGORY_EVENT_CLIPS,
    TIER_SUBCATEGORY_THUMBNAILS,
    TIER_SUBCATEGORY_TIMELAPSE,
)

# Snapshot domains are nested one level deeper, under <tier>/snapshots/<domain>
SNAPSHOT_DOMAIN_DIRS = tuple(domain.value for domain in SnapshotDomain)

# Tables holding rows keyed by camera_identifier
CAMERA_TABLES: tuple[
    type[Recordings | Objects | PostProcessorResults | Files | Motion], ...
] = (Recordings, Objects, PostProcessorResults, Files, Motion)

CONFIG_SNAPSHOT_DOMAINS = (
    CONFIG_FACE_RECOGNITION,
    CONFIG_IMAGE_CLASSIFICATION,
    CONFIG_LICENSE_PLATE_RECOGNITION,
    CONFIG_MOTION_DETECTOR,
    CONFIG_OBJECT_DETECTOR,
)


class OrphanedCameraError(Exception):
    """Raised when data for an orphaned camera cannot be listed or deleted."""


class OrphanedCameraUnavailableError(OrphanedCameraError):
    """Raised when Viseron does not yet know which cameras are configured."""


@dataclass
class OrphanedCamera:
    """Stored data belonging to a camera that is no longer configured."""

    camera_identifier: str
    file_count: int = 0
    size_bytes: int = 0
    database_rows: int = 0
    directories: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON serializable representation."""
        return {
            "camera_identifier": self.camera_identifier,
            "file_count": self.file_count,
            "size_bytes": self.size_bytes,
            "database_rows": self.database_rows,
            "directories": self.directories,
        }


def get_configured_tier_paths(config: dict[str, Any]) -> set[str]:
    """Return every tier path in the storage configuration."""
    paths: set[str] = set()

    def _add_tiers(tiers: list[dict[str, Any]] | None) -> None:
        for tier in tiers or []:
            if path := tier.get(CONFIG_PATH):
                paths.add(path)

    _add_tiers((config.get(CONFIG_RECORDER) or {}).get(CONFIG_TIERS))
    snapshots = config.get(CONFIG_SNAPSHOTS) or {}
    _add_tiers(snapshots.get(CONFIG_TIERS))
    for domain in CONFIG_SNAPSHOT_DOMAINS:
        domain_config = snapshots.get(domain)
        if isinstance(domain_config, dict):
            _add_tiers(domain_config.get(CONFIG_TIERS))
    timelapse = config.get(CONFIG_TIMELAPSE)
    if isinstance(timelapse, dict):
        _add_tiers(timelapse.get(CONFIG_TIERS))

    return paths


def get_camera_directories(tier_paths: set[str], camera_identifier: str) -> list[str]:
    """Return every directory that may hold data for a camera."""
    directories = []
    for tier_path in sorted(tier_paths):
        for subcategory in CAMERA_SUBCATEGORY_DIRS:
            directories.append(os.path.join(tier_path, subcategory, camera_identifier))
        for domain in SNAPSHOT_DOMAIN_DIRS:
            directories.append(
                os.path.join(
                    tier_path, TIER_CATEGORY_SNAPSHOTS, domain, camera_identifier
                )
            )
    return directories


def _scan_tier_paths(tier_paths: set[str]) -> set[str]:
    """Return camera identifiers that have a directory in any tier path."""
    identifiers: set[str] = set()
    for tier_path in tier_paths:
        for subcategory in CAMERA_SUBCATEGORY_DIRS:
            identifiers |= _list_directory_names(os.path.join(tier_path, subcategory))
        for domain in SNAPSHOT_DOMAIN_DIRS:
            identifiers |= _list_directory_names(
                os.path.join(tier_path, TIER_CATEGORY_SNAPSHOTS, domain)
            )
    return identifiers


def _list_directory_names(path: str) -> set[str]:
    """Return the names of the subdirectories of path."""
    try:
        with os.scandir(path) as entries:
            return {entry.name for entry in entries if entry.is_dir()}
    except OSError:
        return set()


def _database_identifiers(session: Session) -> set[str]:
    """Return every camera identifier referenced by the database."""
    identifiers: set[str] = set()
    for table in CAMERA_TABLES:
        identifiers |= {
            row[0]
            for row in session.execute(select(table.camera_identifier).distinct()).all()
            if row[0]
        }
    return identifiers


def _database_tier_paths(session: Session, camera_identifier: str) -> set[str]:
    """Return the tier paths the database has seen for a camera.

    Cameras may override the tier paths in their own configuration, which is gone
    once the camera is removed. The rows in Files are the only remaining record.
    """
    return {
        row[0]
        for row in session.execute(
            select(Files.tier_path)
            .where(Files.camera_identifier == camera_identifier)
            .distinct()
        ).all()
        if row[0]
    }


def _count_database_rows(session: Session, camera_identifier: str) -> int:
    """Return the number of database rows belonging to a camera."""
    total = 0
    for table in CAMERA_TABLES:
        total += (
            session.execute(
                select(func.count())  # pylint: disable=not-callable
                .select_from(table)
                .where(table.camera_identifier == camera_identifier)
            ).scalar()
            or 0
        )
    return total


def _directory_size(path: str) -> tuple[int, int]:
    """Return the number of files and total size in bytes below path."""
    file_count = 0
    size_bytes = 0
    for root, _, files in os.walk(path):
        for file in files:
            file_count += 1
            try:
                size_bytes += os.path.getsize(os.path.join(root, file))
            except OSError:
                continue
    return file_count, size_bytes


def _validate_identifier(camera_identifier: str) -> None:
    """Raise if the identifier cannot be used to build a path."""
    if not CAMERA_IDENTIFIER_PATTERN.match(camera_identifier):
        raise OrphanedCameraError(f"Invalid camera identifier: {camera_identifier}")


def _configured_identifiers(vis: Viseron) -> set[str]:
    """Return every camera identifier known to the configuration."""
    return set(vis.domain_registry.get_identifiers(CAMERA_DOMAIN))


def _assert_setup_complete(vis: Viseron) -> None:
    """Raise unless every component has finished setting up.

    A camera is only known once the component that owns it has been set up, so
    until then a perfectly valid camera is indistinguishable from a removed one.
    """
    if vis.safe_mode:
        raise OrphanedCameraUnavailableError(
            "Viseron is running in safe mode, the configuration could not be read"
        )

    if components := sorted(vis.data[LOADING]):
        raise OrphanedCameraUnavailableError(
            f"Components are still setting up: {', '.join(components)}. "
            "Their cameras are not known yet."
        )

    if components := sorted(vis.data[FAILED]):
        raise OrphanedCameraUnavailableError(
            f"Components failed to set up: {', '.join(components)}. "
            "Their cameras cannot be told apart from removed ones, "
            "fix the configuration before cleaning up."
        )


def get_orphaned_cameras(vis: Viseron, storage: Storage) -> list[OrphanedCamera]:
    """Return stored data for every camera that is no longer configured."""
    _assert_setup_complete(vis)

    configured = _configured_identifiers(vis)
    tier_paths = get_configured_tier_paths(storage.config)

    with storage.get_session() as session:
        identifiers = _database_identifiers(session) | _scan_tier_paths(tier_paths)
        orphaned = []
        for camera_identifier in sorted(identifiers - configured):
            if not CAMERA_IDENTIFIER_PATTERN.match(camera_identifier):
                LOGGER.debug(
                    "Skipping unexpected camera identifier %s", camera_identifier
                )
                continue
            orphaned.append(
                _build_orphaned_camera(session, tier_paths, camera_identifier)
            )

    return orphaned


def _build_orphaned_camera(
    session: Session, tier_paths: set[str], camera_identifier: str
) -> OrphanedCamera:
    """Collect the directories and usage of a single orphaned camera."""
    all_tier_paths = tier_paths | _database_tier_paths(session, camera_identifier)
    orphaned = OrphanedCamera(
        camera_identifier=camera_identifier,
        database_rows=_count_database_rows(session, camera_identifier),
    )
    for directory in get_camera_directories(all_tier_paths, camera_identifier):
        if not os.path.isdir(directory):
            continue
        file_count, size_bytes = _directory_size(directory)
        orphaned.directories.append(directory)
        orphaned.file_count += file_count
        orphaned.size_bytes += size_bytes
    return orphaned


def delete_orphaned_camera(
    vis: Viseron, storage: Storage, camera_identifier: str
) -> OrphanedCamera:
    """Delete all stored data for a camera that is no longer configured.

    Returns what was deleted. Raises OrphanedCameraError if the camera is still
    configured, so that a running camera can never be wiped by mistake.
    """
    _validate_identifier(camera_identifier)
    _assert_setup_complete(vis)

    if camera_identifier in _configured_identifiers(vis):
        raise OrphanedCameraError(
            f"Camera {camera_identifier} is still configured, refusing to delete it"
        )

    tier_paths = get_configured_tier_paths(storage.config)
    with storage.get_session() as session:
        deleted = _build_orphaned_camera(session, tier_paths, camera_identifier)

        # Let OSError propagate so a failed delete is not reported as a success
        for directory in deleted.directories:
            LOGGER.debug("Deleting orphaned camera directory %s", directory)
            shutil.rmtree(directory)

        # MotionContours has no camera_identifier, it is linked through Motion
        session.execute(
            delete(MotionContours).where(
                MotionContours.motion_id.in_(
                    select(Motion.id).where(
                        Motion.camera_identifier == camera_identifier
                    )
                )
            )
        )
        for table in CAMERA_TABLES:
            session.execute(
                delete(table).where(table.camera_identifier == camera_identifier)
            )
        session.commit()

    LOGGER.info(
        "Deleted orphaned camera %s: %d files, %d bytes, %d database rows",
        camera_identifier,
        deleted.file_count,
        deleted.size_bytes,
        deleted.database_rows,
    )
    return deleted
