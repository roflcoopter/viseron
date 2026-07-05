"""Test logical file API handler."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import Mock

from viseron.components.storage.const import (
    CONFIG_PATH,
    TIER_CATEGORY_RECORDER,
    TIER_SUBCATEGORY_SEGMENTS,
)
from viseron.components.storage.files import repair_file_row
from viseron.components.storage.models import Files
from viseron.components.webserver.api.v1.files import (
    authorize_file_request,
    resolve_file_id,
)
from viseron.helpers import utcnow


class FakeSession:
    """Small context-manager session for file resolver tests."""

    def __init__(self, file: Files | None):
        self.file = file
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, *_exc_info):
        """Exit context manager."""

    def get(self, model, file_id: int):
        """Get a model by primary key."""
        if model is Files and self.file and self.file.id == file_id:
            return self.file
        return None

    def commit(self) -> None:
        """Commit transaction."""
        self.committed = True

    def rollback(self) -> None:
        """Rollback transaction."""
        self.rolled_back = True


def _make_file(path: Path, tier_path: Path, *, size: int | None = None) -> Files:
    """Make a Files row."""
    return Files(
        id=1,
        tier_id=0,
        tier_path=str(tier_path),
        camera_identifier="cam1",
        category=TIER_CATEGORY_RECORDER,
        subcategory=TIER_SUBCATEGORY_SEGMENTS,
        path=str(path),
        directory=str(path.parent),
        filename=path.name,
        size=path.stat().st_size if size is None and path.exists() else size or 0,
        duration=5,
        orig_ctime=utcnow(),
    )


def _storage_with_tiers(*tier_paths: Path) -> Mock:
    """Make storage with configured tier handlers."""
    storage = Mock()
    storage.camera_tier_handlers = {
        "cam1": {
            TIER_CATEGORY_RECORDER: [
                {TIER_SUBCATEGORY_SEGMENTS: Mock(tier={CONFIG_PATH: str(tier_path)})}
                for tier_path in tier_paths
            ]
        }
    }
    return storage


def _segment_path(tier_path: Path, filename: str = "1.m4s") -> Path:
    """Return segment path under a configured tier."""
    return (
        tier_path
        / TIER_CATEGORY_RECORDER
        / TIER_SUBCATEGORY_SEGMENTS
        / "cam1"
        / filename
    )


def test_resolve_file_id_serves_existing_path(tmp_path: Path) -> None:
    """Test resolving an existing path."""
    tier = tmp_path / "tier1"
    segment = _segment_path(tier)
    segment.parent.mkdir(parents=True)
    segment.write_bytes(b"test")

    file = _make_file(segment, tier)
    session = FakeSession(file)
    resolved_file = resolve_file_id(lambda: session, _storage_with_tiers(tier), 1)

    assert resolved_file is not None
    assert resolved_file.path == str(segment)
    assert not session.committed


def test_resolve_file_id_returns_moved_tier_path_read_only(tmp_path: Path) -> None:
    """Test resolving a moved file queues repair without updating the Files row."""
    tier1 = tmp_path / "tier1"
    tier2 = tmp_path / "tier2"
    original_segment = _segment_path(tier1)
    moved_segment = _segment_path(tier2)
    moved_segment.parent.mkdir(parents=True)
    moved_segment.write_bytes(b"moved")

    file = _make_file(original_segment, tier1)
    session = FakeSession(file)
    storage = _storage_with_tiers(tier1, tier2)
    resolved_file = resolve_file_id(
        lambda: session,
        storage,
        1,
    )

    assert resolved_file is not None
    assert resolved_file.path == str(moved_segment)
    assert file.tier_id == 0
    assert file.tier_path == str(tier1)
    assert file.path == str(original_segment)
    assert not session.committed
    storage.queue_file_repair.assert_called_once_with(1)


def test_repair_file_row_updates_moved_tier_path(tmp_path: Path) -> None:
    """Test repairing a stale Files row."""
    tier1 = tmp_path / "tier1"
    tier2 = tmp_path / "tier2"
    original_segment = _segment_path(tier1)
    moved_segment = _segment_path(tier2)
    moved_segment.parent.mkdir(parents=True)
    moved_segment.write_bytes(b"moved")

    file = _make_file(original_segment, tier1)

    assert repair_file_row(_storage_with_tiers(tier1, tier2), file) is True
    assert file.tier_id == 1
    assert file.tier_path == str(tier2)
    assert file.path == str(moved_segment)
    assert file.directory == str(moved_segment.parent)
    assert file.filename == moved_segment.name
    assert file.size == len(b"moved")


def test_resolve_file_id_rejects_path_outside_configured_tiers(tmp_path: Path) -> None:
    """Test rejecting a row that points outside configured storage roots."""
    tier = tmp_path / "tier1"
    outside = tmp_path / "outside" / "1.m4s"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(b"outside")

    file = _make_file(outside, outside.parent)
    session = FakeSession(file)
    resolved_file = resolve_file_id(lambda: session, _storage_with_tiers(tier), 1)

    assert resolved_file is None
    assert not session.committed


def test_resolve_file_id_missing_file_returns_none(tmp_path: Path) -> None:
    """Test resolving a missing file."""
    tier = tmp_path / "tier1"
    file = _make_file(_segment_path(tier), tier)
    session = FakeSession(file)

    assert resolve_file_id(lambda: session, _storage_with_tiers(tier), 1) is None


class FakeAuthHandler:
    """Small async-compatible handler for auth helper tests."""

    def __init__(self, *, camera: Mock | None, camera_token_valid: bool):
        self.webserver = Mock(auth=Mock())
        self.camera = camera
        self.camera_token_valid = camera_token_valid
        self.failed = None
        self.error_status = None
        self.error_reason = None

    async def run_in_executor(self, func, *args):
        """Run synchronously for tests."""
        return func(*args)

    def validate_auth_header(self) -> bool:
        """Return if API auth is valid."""
        return False

    def _get_camera(self, camera_identifier: str, *, failed: bool = False):  # noqa: ARG002
        """Get camera by identifier."""
        self.failed = failed
        if self.camera and self.camera.identifier == camera_identifier:
            return self.camera
        return None

    def validate_camera_token(self, camera: Mock) -> bool:
        """Validate camera token."""
        return bool(camera and self.camera_token_valid)

    def response_error(self, status, reason: str) -> None:
        """Store error response."""
        self.error_status = status
        self.error_reason = reason


def test_authorize_file_request_rejects_wrong_camera_token() -> None:
    """Test wrong camera token is rejected."""
    camera = Mock(identifier="cam1")
    handler = FakeAuthHandler(camera=camera, camera_token_valid=False)

    assert not asyncio.run(authorize_file_request(handler, "cam1"))
    assert handler.error_status.value == 401
    assert handler.error_reason == "Unauthorized"


def test_authorize_file_request_accepts_camera_token() -> None:
    """Test camera token is accepted."""
    camera = Mock(identifier="cam1")
    handler = FakeAuthHandler(camera=camera, camera_token_valid=True)

    assert asyncio.run(authorize_file_request(handler, "cam1"))
    assert handler.error_status is None


def test_authorize_file_request_can_include_failed_cameras() -> None:
    """Test failed-camera lookup flag is passed through."""
    camera = Mock(identifier="cam1")
    handler = FakeAuthHandler(camera=camera, camera_token_valid=True)

    assert asyncio.run(authorize_file_request(handler, "cam1", failed=True))
    assert handler.failed is True
