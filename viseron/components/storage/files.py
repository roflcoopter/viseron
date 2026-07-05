"""Helpers for registering storage files in the database."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert

from viseron.components.storage.const import (
    CONFIG_PATH,
    TIER_CATEGORY_RECORDER,
    TIER_CATEGORY_SNAPSHOTS,
    TIER_CATEGORY_TIMELAPSE,
    TIER_SUBCATEGORY_EVENT_CLIPS,
    TIER_SUBCATEGORY_FACE_RECOGNITION,
    TIER_SUBCATEGORY_LICENSE_PLATE_RECOGNITION,
    TIER_SUBCATEGORY_MOTION_DETECTOR,
    TIER_SUBCATEGORY_OBJECT_DETECTOR,
    TIER_SUBCATEGORY_SEGMENTS,
    TIER_SUBCATEGORY_THUMBNAILS,
    TIER_SUBCATEGORY_TIMELAPSE,
)
from viseron.components.storage.models import Files
from viseron.helpers import utcnow

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

    from viseron.components.storage import Storage

LOGGER = logging.getLogger(__name__)

ALLOWED_FILE_TYPES = frozenset(
    {
        (TIER_CATEGORY_RECORDER, TIER_SUBCATEGORY_SEGMENTS),
        (TIER_CATEGORY_RECORDER, TIER_SUBCATEGORY_EVENT_CLIPS),
        (TIER_CATEGORY_RECORDER, TIER_SUBCATEGORY_THUMBNAILS),
        (TIER_CATEGORY_SNAPSHOTS, TIER_SUBCATEGORY_FACE_RECOGNITION),
        (TIER_CATEGORY_SNAPSHOTS, TIER_SUBCATEGORY_OBJECT_DETECTOR),
        (TIER_CATEGORY_SNAPSHOTS, TIER_SUBCATEGORY_LICENSE_PLATE_RECOGNITION),
        (TIER_CATEGORY_SNAPSHOTS, TIER_SUBCATEGORY_MOTION_DETECTOR),
        (TIER_CATEGORY_TIMELAPSE, TIER_SUBCATEGORY_TIMELAPSE),
    }
)


@dataclass(frozen=True)
class _ConfiguredFileTier:
    """Configured storage tier containing a file."""

    tier_id: int
    tier_path: str
    root: str


@dataclass(frozen=True)
class ResolvedFile:
    """Resolved storage file."""

    file_id: int
    camera_identifier: str
    category: str
    subcategory: str
    path: str
    size: int


@dataclass(frozen=True)
class _ResolvedFilePath:
    """Resolved path and tier for a Files row."""

    path: str
    tier: _ConfiguredFileTier
    stale: bool


def _path_contains(parent: str, child: str) -> bool:
    """Return if child is inside parent, resolving symlinks."""
    try:
        parent_realpath = os.path.realpath(parent)
        child_realpath = os.path.realpath(child)
        return os.path.commonpath([parent_realpath, child_realpath]) == parent_realpath
    except ValueError:
        return False


def _configured_file_tiers(
    storage: Storage,
    camera_identifier: str,
    category: str,
    subcategory: str,
) -> list[_ConfiguredFileTier]:
    """Return configured tiers for a storage file type."""
    try:
        tier_handlers = storage.camera_tier_handlers[camera_identifier][category]
    except KeyError:
        return []

    tiers: list[_ConfiguredFileTier] = []
    for tier_id, tier_handler in enumerate(tier_handlers):
        if subcategory not in tier_handler:
            continue
        subcategory_handler = tier_handler[subcategory]
        tier_path = subcategory_handler.tier[CONFIG_PATH]
        root = getattr(subcategory_handler, "_path", None)
        if not isinstance(root, (str, bytes, os.PathLike)):
            root = os.path.join(tier_path, category, subcategory, camera_identifier)
        tiers.append(
            _ConfiguredFileTier(
                tier_id=tier_id,
                tier_path=tier_path,
                root=os.path.normpath(root),
            )
        )
    return tiers


def file_tier_for_path(
    storage: Storage,
    camera_identifier: str,
    category: str,
    subcategory: str,
    path: str,
) -> _ConfiguredFileTier | None:
    """Return the configured tier containing a file path."""
    normalized_path = os.path.normpath(path)
    for tier in _configured_file_tiers(
        storage, camera_identifier, category, subcategory
    ):
        if _path_contains(tier.root, normalized_path):
            return tier
    return None


def _matching_tier(
    path: str, tiers: list[_ConfiguredFileTier]
) -> _ConfiguredFileTier | None:
    """Return configured tier containing path."""
    normalized_path = os.path.normpath(path)
    for tier in tiers:
        if _path_contains(tier.root, normalized_path):
            return tier
    return None


def _path_from_file_row(file: Files, tiers: list[_ConfiguredFileTier]) -> str | None:
    """Resolve current or recoverable path for a Files row."""
    current_path = os.path.normpath(file.path)
    current_tier = _matching_tier(current_path, tiers)
    if current_tier and os.path.isfile(current_path):
        return current_path

    stored_tier_path = os.path.normpath(file.tier_path)
    if not _path_contains(stored_tier_path, current_path):
        LOGGER.warning(
            "Files row %s path %s is outside stored tier path %s",
            file.id,
            file.path,
            file.tier_path,
        )
        return None

    relative_path = os.path.relpath(current_path, stored_tier_path)
    for tier in tiers:
        candidate_path = os.path.normpath(os.path.join(tier.tier_path, relative_path))
        if not _path_contains(tier.root, candidate_path):
            continue
        if os.path.isfile(candidate_path):
            return candidate_path
    return None


def _resolved_path_from_file_row(
    file: Files, tiers: list[_ConfiguredFileTier]
) -> _ResolvedFilePath | None:
    """Resolve a Files row path without mutating the row."""
    current_path = os.path.normpath(file.path)
    current_tier = _matching_tier(current_path, tiers)
    if current_tier and os.path.isfile(current_path):
        return _ResolvedFilePath(current_path, current_tier, stale=False)

    resolved_path = _path_from_file_row(file, tiers)
    if resolved_path is None:
        return None

    resolved_tier = _matching_tier(resolved_path, tiers)
    if resolved_tier is None:
        return None
    return _ResolvedFilePath(resolved_path, resolved_tier, stale=True)


def _update_file_row(file: Files, path: str, tier: _ConfiguredFileTier) -> None:
    """Update a Files row after recovery or tier mismatch."""
    file.tier_id = tier.tier_id
    file.tier_path = tier.tier_path
    file.path = path
    file.directory = os.path.dirname(path)
    file.filename = os.path.basename(path)
    file.size = os.path.getsize(path)


def repair_file_row(storage: Storage, file: Files) -> bool:
    """Repair a stale Files row if its file is recoverable in configured tiers."""
    tiers = _configured_file_tiers(
        storage,
        file.camera_identifier,
        file.category,
        file.subcategory,
    )
    if not tiers:
        return False

    resolved_path = _resolved_path_from_file_row(file, tiers)
    if resolved_path is None or not resolved_path.stale:
        return False

    _update_file_row(file, resolved_path.path, resolved_path.tier)
    return True


def _relative_artifact_path(
    path: str,
    tiers: list[_ConfiguredFileTier],
    category: str,
    subcategory: str,
    camera_identifier: str,
) -> str | None:
    """Return an artifact path relative to its camera/category root."""
    normalized_path = os.path.normpath(path)
    for tier in tiers:
        if _path_contains(tier.root, normalized_path):
            return os.path.relpath(normalized_path, os.path.normpath(tier.root))

    marker_parts = [category, subcategory, camera_identifier]
    path_parts = normalized_path.split(os.sep)
    marker_len = len(marker_parts)
    for index in range(len(path_parts) - marker_len, -1, -1):
        if path_parts[index : index + marker_len] == marker_parts:
            relative_parts = path_parts[index + marker_len :]
            if relative_parts:
                return os.path.join(*relative_parts)
    return None


def find_file_id_for_artifact_path(
    session: Session,
    storage: Storage,
    camera_identifier: str,
    category: str,
    subcategory: str,
    path: str | None,
) -> int | None:
    """Find a Files id for a legacy artifact path."""
    if not path:
        return None

    file_id = session.execute(
        select(Files.id)
        .where(Files.path == path)
        .where(Files.camera_identifier == camera_identifier)
        .where(Files.category == category)
        .where(Files.subcategory == subcategory)
    ).scalar_one_or_none()
    if file_id is not None:
        return file_id

    tiers = _configured_file_tiers(storage, camera_identifier, category, subcategory)
    if not tiers:
        return None

    relative_path = _relative_artifact_path(
        path,
        tiers,
        category,
        subcategory,
        camera_identifier,
    )
    if relative_path is None:
        return None

    candidate_paths = [
        os.path.normpath(os.path.join(tier.root, relative_path)) for tier in tiers
    ]
    return session.execute(
        select(Files.id)
        .where(Files.path.in_(candidate_paths))
        .where(Files.camera_identifier == camera_identifier)
        .where(Files.category == category)
        .where(Files.subcategory == subcategory)
        .order_by(Files.tier_id.desc())
        .limit(1)
    ).scalar_one_or_none()


def resolve_file_id(
    get_session: Callable[[], Session],
    storage: Storage,
    file_id: int,
    allowed_file_types: frozenset[tuple[str, str]] = ALLOWED_FILE_TYPES,
) -> ResolvedFile | None:
    """Resolve a logical file id to an on-disk file under configured tiers."""
    with get_session() as session:
        file = session.get(Files, file_id)
        if file is None:
            return None

        if (file.category, file.subcategory) not in allowed_file_types:
            LOGGER.warning(
                "Rejecting Files row %s with unsupported type %s/%s",
                file.id,
                file.category,
                file.subcategory,
            )
            return None

        tiers = _configured_file_tiers(
            storage,
            file.camera_identifier,
            file.category,
            file.subcategory,
        )
        if not tiers:
            LOGGER.warning(
                "No configured tiers for Files row %s type %s/%s camera %s",
                file.id,
                file.category,
                file.subcategory,
                file.camera_identifier,
            )
            return None

        resolved_path = _resolved_path_from_file_row(file, tiers)
        if resolved_path is None:
            return None

        if resolved_path.stale:
            queue_file_repair = getattr(storage, "queue_file_repair", None)
            if callable(queue_file_repair):
                queue_file_repair(file.id)

        return ResolvedFile(
            file_id=file.id,
            camera_identifier=file.camera_identifier,
            category=file.category,
            subcategory=file.subcategory,
            path=resolved_path.path,
            size=os.path.getsize(resolved_path.path),
        )


def upsert_file(
    get_session: Callable[[], Session],
    storage: Storage,
    camera_identifier: str,
    category: str,
    subcategory: str,
    path: str,
    *,
    duration: float | None = None,
) -> int | None:
    """Ensure a published storage file has a Files row and return its id."""
    if not os.path.isfile(path):
        return None

    normalized_path = os.path.normpath(path)
    tier = file_tier_for_path(
        storage,
        camera_identifier,
        category,
        subcategory,
        normalized_path,
    )
    if tier is None:
        LOGGER.warning(
            "Refusing to register %s/%s file %s outside configured tiers for camera %s",
            category,
            subcategory,
            normalized_path,
            camera_identifier,
        )
        return None

    stat_result = os.stat(normalized_path)
    values = {
        "tier_id": tier.tier_id,
        "tier_path": tier.tier_path,
        "camera_identifier": camera_identifier,
        "category": category,
        "subcategory": subcategory,
        "path": normalized_path,
        "directory": os.path.dirname(normalized_path),
        "filename": os.path.basename(normalized_path),
        "size": stat_result.st_size,
        "orig_ctime": utcnow(),
        "duration": duration,
    }
    with get_session() as session:
        stmt = (
            postgresql_insert(Files)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[Files.path],
                set_={
                    "tier_id": values["tier_id"],
                    "tier_path": values["tier_path"],
                    "camera_identifier": values["camera_identifier"],
                    "category": values["category"],
                    "subcategory": values["subcategory"],
                    "directory": values["directory"],
                    "filename": values["filename"],
                    "size": values["size"],
                    "duration": values["duration"],
                },
            )
            .returning(Files.id)
        )
        file_id = session.execute(stmt).scalar_one()
        session.commit()
        return file_id
