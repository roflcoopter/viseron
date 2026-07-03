"""Storage component utility functions."""

from __future__ import annotations

import errno
import os
import shutil
import stat
import threading
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from viseron.components.storage.const import (
    CONFIG_DAYS,
    CONFIG_GB,
    CONFIG_HOURS,
    CONFIG_MB,
    CONFIG_MINUTES,
    CONFIG_PATH,
    CONFIG_SECONDS,
    TIER_CATEGORY_SNAPSHOTS,
    TIER_SUBCATEGORY_EVENT_CLIPS,
    TIER_SUBCATEGORY_SEGMENTS,
    TIER_SUBCATEGORY_THUMBNAILS,
    TIER_SUBCATEGORY_TIMELAPSE,
)
from viseron.events import EventData

if TYPE_CHECKING:
    from types import TracebackType

    from viseron.domains.camera import AbstractCamera, FailedCamera
    from viseron.viseron_types import SnapshotDomain

TEMP_STORAGE_FILE_PREFIX = ".viseron-tmp-"
TRANSIENT_FILESYSTEM_ERRNOS = {
    error_number
    for error_number in (
        errno.EIO,
        getattr(errno, "ESTALE", None),
        errno.ETIMEDOUT,
        errno.ECONNABORTED,
        errno.ECONNRESET,
        errno.ENOTCONN,
        getattr(errno, "EHOSTDOWN", None),
        errno.EHOSTUNREACH,
        errno.ENETDOWN,
        errno.ENETUNREACH,
    )
    if error_number is not None
}


@dataclass(frozen=True)
class AtomicMoveResult:
    """Result of an atomic publish followed by source cleanup."""

    size: int
    published: bool
    source_removed: bool
    source_remove_error: OSError | None = None


def is_storage_temp_file(path: str) -> bool:
    """Return if a path is an internal temporary storage file."""
    return os.path.basename(path).startswith(TEMP_STORAGE_FILE_PREFIX)


def is_transient_filesystem_error(error: OSError) -> bool:
    """Return if an OSError is likely transient on a remote filesystem."""
    return error.errno in TRANSIENT_FILESYSTEM_ERRNOS


def get_storage_temp_path(dst: str) -> str:
    """Return a hidden temporary path in the same directory as dst."""
    directory = os.path.dirname(dst)
    filename = os.path.basename(dst)
    return os.path.join(
        directory,
        f"{TEMP_STORAGE_FILE_PREFIX}{filename}.{os.getpid()}.{uuid.uuid4().hex}",
    )


def fsync_directory(path: str) -> None:
    """Best-effort fsync of a directory."""
    try:
        dir_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


def copy_file_atomic(src: str, dst: str) -> int:
    """Copy src to dst using a same-directory temp file and atomic replace.

    Returns the verified source size.
    """
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    src_size = os.path.getsize(src)
    tmp_dst = get_storage_temp_path(dst)

    def validate_tmp_size() -> None:
        tmp_size = os.path.getsize(tmp_dst)
        if tmp_size != src_size:
            raise OSError(
                f"Copied file size mismatch for {src}: "
                f"expected {src_size}, got {tmp_size}"
            )

    try:
        with open(src, "rb") as src_file, open(tmp_dst, "wb") as dst_file:
            shutil.copyfileobj(src_file, dst_file, length=1024 * 1024)
            dst_file.flush()
            os.fsync(dst_file.fileno())

        validate_tmp_size()
        try:
            os.replace(tmp_dst, dst)
        except OSError as replace_error:
            # Network filesystems can publish the rename server-side but lose the
            # success reply. If the destination now verifies at the expected size,
            # treat the publish as committed instead of retrying a duplicate move.
            try:
                dst_size = os.path.getsize(dst)
            except OSError as stat_error:
                raise replace_error from stat_error
            if dst_size == src_size:
                fsync_directory(os.path.dirname(dst))
                return src_size
            raise replace_error
        fsync_directory(os.path.dirname(dst))
        return src_size
    except Exception:
        try:
            os.remove(tmp_dst)
        except FileNotFoundError:
            pass
        raise


def move_file_atomic(src: str, dst: str) -> AtomicMoveResult:
    """Move src to dst after atomically publishing dst."""
    size = copy_file_atomic(src, dst)
    try:
        # Destination publication is the commit point. Source cleanup can fail on
        # soft/remote mounts after the copy is durable, so report it separately.
        os.remove(src)
    except FileNotFoundError:
        return AtomicMoveResult(size=size, published=True, source_removed=True)
    except OSError as error:
        return AtomicMoveResult(
            size=size,
            published=True,
            source_removed=False,
            source_remove_error=error,
        )
    return AtomicMoveResult(size=size, published=True, source_removed=True)


def path_exists(path: str) -> bool:
    """Return if path exists, propagating non-missing filesystem errors."""
    try:
        os.stat(path)
    except FileNotFoundError:
        return False
    return True


def tier_path_available(path: str) -> bool:
    """Return if a tier path is currently reachable.

    Use stat instead of scandir to avoid directory enumeration on remote filesystems.
    """
    try:
        stat_result = os.stat(path)
    except OSError:
        return False
    return stat.S_ISDIR(stat_result.st_mode)


def raise_if_path_unavailable(path: str) -> None:
    """Raise OSError if the parent directory for path is not available."""
    directory = os.path.dirname(path)
    if directory and not tier_path_available(directory):
        raise OSError(f"Parent directory is unavailable for {path}: {directory}")


def calculate_age(age: dict[str, Any]) -> timedelta:
    """Calculate age in seconds."""
    if not age:
        return timedelta(seconds=0)

    return timedelta(
        days=age[CONFIG_DAYS] or 0,
        hours=age[CONFIG_HOURS] or 0,
        minutes=age[CONFIG_MINUTES] or 0,
        seconds=age.get(CONFIG_SECONDS) or 0,
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


def get_timelapse_path(
    tier: dict[str, Any], camera: AbstractCamera | FailedCamera
) -> str:
    """Get timelapse path for camera."""
    return os.path.join(
        tier[CONFIG_PATH], TIER_SUBCATEGORY_TIMELAPSE, camera.identifier
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
