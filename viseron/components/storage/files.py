"""Helpers for registering storage files in the database."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select, update
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
from viseron.components.storage.models import FileLocations, FileLocationState, Files
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
class UpsertedFile:
    """Result of publishing a logical file and physical location."""

    file_id: int
    created: bool


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


def _best_configured_location(
    locations: list[FileLocations],
    tiers: list[_ConfiguredFileTier],
) -> FileLocations | None:
    """Return the best available physical location for a logical file."""
    tier_by_id = {tier.tier_id: tier for tier in tiers}

    def sort_key(location: FileLocations) -> tuple[int, int, int]:
        configured = 0 if location.tier_id in tier_by_id else 1
        state_rank = 0 if location.state == FileLocationState.AVAILABLE.value else 1
        return configured, state_rank, location.tier_id

    for location in sorted(locations, key=sort_key):
        tier = tier_by_id.get(location.tier_id)
        if tier is None:
            continue
        if not _path_contains(tier.root, location.path):
            LOGGER.warning(
                "File location %s path %s is outside configured tier root %s",
                location.id,
                location.path,
                tier.root,
            )
            continue
        try:
            if os.path.isfile(location.path):
                return location
        except OSError as error:
            LOGGER.warning(
                "Skipping unavailable file location %s (%s): %s",
                location.id,
                location.path,
                error,
            )
            continue
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


def _update_shadow_from_location(file: Files, location: FileLocations) -> None:
    """Maintain legacy Files physical columns from a preferred location."""
    file.tier_id = location.tier_id
    file.tier_path = location.tier_path
    file.path = location.path
    file.directory = location.directory
    file.filename = location.filename
    file.size = location.size


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


def repair_file_locations(session: Session, storage: Storage, file: Files) -> bool:
    """Repair stale logical file metadata by adding a recovered location."""
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

    size = os.path.getsize(resolved_path.path)
    upsert_file_location(
        session,
        file.id,
        resolved_path.tier.tier_id,
        resolved_path.tier.tier_path,
        resolved_path.path,
        size,
        state=FileLocationState.AVAILABLE.value,
    )
    location = session.execute(
        select(FileLocations).where(FileLocations.path == resolved_path.path)
    ).scalar_one()
    _update_shadow_from_location(file, location)
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
        select(FileLocations.file_id)
        .where(FileLocations.path == path)
        .join(Files, Files.id == FileLocations.file_id)
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
        select(FileLocations.file_id)
        .where(FileLocations.path.in_(candidate_paths))
        .join(Files, Files.id == FileLocations.file_id)
        .where(Files.camera_identifier == camera_identifier)
        .where(Files.category == category)
        .where(Files.subcategory == subcategory)
        .order_by(FileLocations.tier_id.desc())
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
            LOGGER.debug("Files row %s was not found", file_id)
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

        locations: list[FileLocations] = []
        execute = getattr(session, "execute", None)
        if callable(execute):
            locations = (
                execute(
                    select(FileLocations)
                    .where(FileLocations.file_id == file.id)
                    .where(FileLocations.state == FileLocationState.AVAILABLE.value)
                )
                .scalars()
                .all()
            )
        location = _best_configured_location(locations, tiers)
        if location is not None:
            return ResolvedFile(
                file_id=file.id,
                camera_identifier=file.camera_identifier,
                category=file.category,
                subcategory=file.subcategory,
                path=location.path,
                size=os.path.getsize(location.path),
            )

        resolved_path = _resolved_path_from_file_row(file, tiers)
        if resolved_path is None:
            LOGGER.warning(
                "Could not resolve Files row %s to an on-disk file "
                "(camera=%s, type=%s/%s, path=%s, tier_id=%s, tier_path=%s)",
                file.id,
                file.camera_identifier,
                file.category,
                file.subcategory,
                file.path,
                file.tier_id,
                file.tier_path,
            )
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


def upsert_file_location(
    session: Session,
    file_id: int,
    tier_id: int,
    tier_path: str,
    path: str,
    size: int,
    *,
    state: str = FileLocationState.AVAILABLE.value,
) -> int:
    """Upsert a physical file location and return its id."""
    values = {
        "file_id": file_id,
        "tier_id": tier_id,
        "tier_path": tier_path,
        "path": path,
        "directory": os.path.dirname(path),
        "filename": os.path.basename(path),
        "size": size,
        "state": state,
    }
    stmt = (
        postgresql_insert(FileLocations)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[FileLocations.path],
            set_={
                "file_id": values["file_id"],
                "tier_id": values["tier_id"],
                "tier_path": values["tier_path"],
                "directory": values["directory"],
                "filename": values["filename"],
                "size": values["size"],
                "state": values["state"],
            },
        )
        .returning(FileLocations.id)
    )
    result = session.execute(stmt)
    scalar_one = getattr(result, "scalar_one", None)
    if callable(scalar_one):
        return scalar_one()
    return 0


def _delete_logical_file_if_unlocated(session: Session, file_id: int) -> None:
    """Delete a logical Files row if it has no physical locations."""
    location_count = session.execute(
        select(func.count())
        .select_from(FileLocations)
        .where(FileLocations.file_id == file_id)
    ).scalar_one()
    if location_count == 0:
        session.execute(delete(Files).where(Files.id == file_id))


def delete_file_location_by_path(
    session: Session,
    path: str,
    *,
    missing_state: str | None = None,
    delete_logical: bool = True,
) -> int | None:
    """Delete or mark a physical location by path and clean up orphan logical files."""
    result = session.execute(
        select(FileLocations.file_id).where(FileLocations.path == path)
    )
    scalar_one_or_none = getattr(result, "scalar_one_or_none", None)
    if not callable(scalar_one_or_none):
        return None
    file_id = scalar_one_or_none()
    if file_id is None:
        return None

    if missing_state is None:
        session.execute(delete(FileLocations).where(FileLocations.path == path))
    else:
        session.execute(
            update(FileLocations)
            .where(FileLocations.path == path)
            .values(state=missing_state)
        )
    if missing_state is None and delete_logical:
        _delete_logical_file_if_unlocated(session, file_id)
    return file_id


def upsert_file_at_location(
    get_session: Callable[[], Session],
    camera_identifier: str,
    category: str,
    subcategory: str,
    tier_id: int,
    tier_path: str,
    path: str,
    *,
    orig_ctime=None,
    duration: float | None = None,
) -> UpsertedFile | None:
    """Ensure a logical file and physical location exist."""
    if not os.path.isfile(path):
        return None

    normalized_path = os.path.normpath(path)
    stat_result = os.stat(normalized_path)
    filename = os.path.basename(normalized_path)
    values = {
        "tier_id": tier_id,
        "tier_path": tier_path,
        "camera_identifier": camera_identifier,
        "category": category,
        "subcategory": subcategory,
        "path": normalized_path,
        "directory": os.path.dirname(normalized_path),
        "filename": filename,
        "size": stat_result.st_size,
        "orig_ctime": orig_ctime or utcnow(),
        "duration": duration,
    }
    with get_session() as session:
        existing_file_id = session.execute(
            select(Files.id)
            .where(Files.camera_identifier == camera_identifier)
            .where(Files.category == category)
            .where(Files.subcategory == subcategory)
            .where(Files.filename == filename)
        ).scalar_one_or_none()
        created = existing_file_id is None
        stmt = (
            postgresql_insert(Files)
            .values(**values)
            .on_conflict_do_nothing(
                index_elements=[
                    Files.camera_identifier,
                    Files.category,
                    Files.subcategory,
                    Files.filename,
                ],
            )
            .returning(Files.id)
        )
        inserted_file_id = session.execute(stmt).scalar_one_or_none()
        created = inserted_file_id is not None
        file_id = inserted_file_id or existing_file_id
        if file_id is None:
            file_id = session.execute(
                select(Files.id)
                .where(Files.camera_identifier == camera_identifier)
                .where(Files.category == category)
                .where(Files.subcategory == subcategory)
                .where(Files.filename == filename)
            ).scalar_one()
            created = False

        upsert_file_location(
            session,
            file_id,
            tier_id,
            tier_path,
            normalized_path,
            stat_result.st_size,
            state=FileLocationState.AVAILABLE.value,
        )

        update_values = {
            "tier_id": values["tier_id"],
            "tier_path": values["tier_path"],
            "path": values["path"],
            "directory": values["directory"],
            "size": values["size"],
        }
        if created or duration is not None:
            update_values["orig_ctime"] = values["orig_ctime"]
            update_values["duration"] = values["duration"]
        session.execute(update(Files).where(Files.id == file_id).values(update_values))
        session.commit()
        return UpsertedFile(file_id=file_id, created=created)


def upsert_file_with_location(
    get_session: Callable[[], Session],
    storage: Storage,
    camera_identifier: str,
    category: str,
    subcategory: str,
    path: str,
    *,
    orig_ctime=None,
    duration: float | None = None,
) -> UpsertedFile | None:
    """Ensure a logical file and physical location exist by configured path."""
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
    return upsert_file_at_location(
        get_session,
        camera_identifier,
        category,
        subcategory,
        tier.tier_id,
        tier.tier_path,
        normalized_path,
        orig_ctime=orig_ctime,
        duration=duration,
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
    upserted_file = upsert_file_with_location(
        get_session,
        storage,
        camera_identifier,
        category,
        subcategory,
        path,
        duration=duration,
    )
    return upserted_file.file_id if upserted_file else None
