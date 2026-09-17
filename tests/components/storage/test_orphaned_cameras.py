"""Test the orphaned_cameras module."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from viseron.components.storage.models import (
    Files,
    Motion,
    MotionContours,
    Objects,
    PostProcessorResults,
    Recordings,
)
from viseron.components.storage.orphaned_cameras import (
    OrphanedCameraError,
    OrphanedCameraUnavailableError,
    delete_orphaned_camera,
    get_camera_directories,
    get_configured_tier_paths,
    get_orphaned_cameras,
)
from viseron.const import FAILED, LOADING
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.helpers import utcnow

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session, sessionmaker


def _write_file(path: str, size: int = 1024) -> None:
    """Create a file of the given size, creating parent directories."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as file:
        file.write(b"0" * size)


def _tier_config(tier_path: str) -> dict:
    """Return a minimal storage config with a single tier."""
    return {
        "recorder": {"tiers": [{"path": tier_path}]},
        "snapshots": {"tiers": [{"path": tier_path}]},
        "timelapse": {"tiers": [{"path": tier_path}]},
    }


def _mock_storage(tier_path: str, get_db_session: sessionmaker[Session]) -> MagicMock:
    """Return a Storage mock backed by the test database."""
    storage = MagicMock()
    storage.config = _tier_config(tier_path)
    storage.get_session = get_db_session
    return storage


def _mock_vis(configured: list[str]) -> MagicMock:
    """Return a Viseron mock with the given cameras configured."""
    vis = MagicMock()
    vis.safe_mode = False
    vis.data = {LOADING: {}, FAILED: {}}
    vis.domain_registry.get_identifiers.return_value = configured
    return vis


def _add_file(session: Session, tier_path: str, camera_identifier: str, path: str):
    """Insert a Files row."""
    session.add(
        Files(
            tier_id=0,
            tier_path=tier_path,
            camera_identifier=camera_identifier,
            category="recorder",
            subcategory="segments",
            path=path,
            directory=os.path.dirname(path),
            filename=os.path.basename(path),
            size=1024,
            orig_ctime=utcnow(),
        )
    )


def test_get_configured_tier_paths() -> None:
    """Test that every tier path in the config is found."""
    config = {
        "recorder": {"tiers": [{"path": "/tier1"}, {"path": "/tier2"}]},
        "snapshots": {
            "tiers": [{"path": "/tier1"}],
            "face_recognition": {"tiers": [{"path": "/faces"}]},
            "object_detector": None,
        },
        "timelapse": {"tiers": [{"path": "/lapse"}]},
    }
    assert get_configured_tier_paths(config) == {
        "/tier1",
        "/tier2",
        "/faces",
        "/lapse",
    }


def test_get_configured_tier_paths_empty() -> None:
    """Test that an empty config yields no tier paths."""
    assert get_configured_tier_paths({}) == set()
    assert get_configured_tier_paths({"timelapse": None}) == set()


def test_get_camera_directories() -> None:
    """Test that all per-camera directories of a tier are returned."""
    directories = get_camera_directories({"/tier1"}, "camera_3")
    assert "/tier1/segments/camera_3" in directories
    assert "/tier1/event_clips/camera_3" in directories
    assert "/tier1/thumbnails/camera_3" in directories
    assert "/tier1/timelapse/camera_3" in directories
    assert "/tier1/snapshots/object_detector/camera_3" in directories
    assert "/tier1/snapshots/face_recognition/camera_3" in directories
    assert len(directories) == len(set(directories))


class TestGetOrphanedCameras:
    """Test get_orphaned_cameras."""

    def test_finds_camera_removed_from_config(
        self, tmp_path: Path, get_db_session: sessionmaker[Session]
    ) -> None:
        """Test that a camera with data but no config is reported."""
        tier_path = str(tmp_path)
        _write_file(os.path.join(tier_path, "segments/camera_1/file.m4s"))
        _write_file(os.path.join(tier_path, "segments/camera_3/file.m4s"), 2048)
        _write_file(os.path.join(tier_path, "event_clips/camera_3/clip.mp4"), 512)

        with get_db_session() as session:
            _add_file(
                session,
                tier_path,
                "camera_3",
                os.path.join(tier_path, "segments/camera_3/file.m4s"),
            )
            session.commit()

        orphaned = get_orphaned_cameras(
            _mock_vis(["camera_1"]), _mock_storage(tier_path, get_db_session)
        )

        assert [camera.camera_identifier for camera in orphaned] == ["camera_3"]
        assert orphaned[0].file_count == 2
        assert orphaned[0].size_bytes == 2560
        assert orphaned[0].database_rows == 1
        assert sorted(orphaned[0].directories) == [
            os.path.join(tier_path, "event_clips/camera_3"),
            os.path.join(tier_path, "segments/camera_3"),
        ]

    def test_ignores_configured_cameras(
        self, tmp_path: Path, get_db_session: sessionmaker[Session]
    ) -> None:
        """Test that a camera that is still configured is never reported."""
        tier_path = str(tmp_path)
        _write_file(os.path.join(tier_path, "segments/camera_1/file.m4s"))

        orphaned = get_orphaned_cameras(
            _mock_vis(["camera_1"]), _mock_storage(tier_path, get_db_session)
        )
        assert orphaned == []

    def test_finds_camera_with_database_rows_only(
        self, tmp_path: Path, get_db_session: sessionmaker[Session]
    ) -> None:
        """Test that a camera with rows but no files on disk is reported."""
        tier_path = str(tmp_path)
        with get_db_session() as session:
            session.add(
                Recordings(
                    camera_identifier="camera_3",
                    start_time=utcnow(),
                    adjusted_start_time=utcnow(),
                )
            )
            session.commit()

        orphaned = get_orphaned_cameras(
            _mock_vis([]), _mock_storage(tier_path, get_db_session)
        )
        assert [camera.camera_identifier for camera in orphaned] == ["camera_3"]
        assert orphaned[0].file_count == 0
        assert orphaned[0].directories == []
        assert orphaned[0].database_rows == 1

    def test_uses_tier_paths_from_database(
        self, tmp_path: Path, get_db_session: sessionmaker[Session]
    ) -> None:
        """Test that a tier path only known to the database is searched.

        A camera may override the tier paths in its own config, which is gone
        once the camera is removed from the configuration.
        """
        tier_path = str(tmp_path / "tier1")
        custom_path = str(tmp_path / "custom")
        os.makedirs(tier_path, exist_ok=True)
        file_path = os.path.join(custom_path, "segments/camera_3/file.m4s")
        _write_file(file_path, 128)

        with get_db_session() as session:
            _add_file(session, custom_path, "camera_3", file_path)
            session.commit()

        orphaned = get_orphaned_cameras(
            _mock_vis([]), _mock_storage(tier_path, get_db_session)
        )
        assert orphaned[0].directories == [
            os.path.join(custom_path, "segments/camera_3")
        ]
        assert orphaned[0].size_bytes == 128

    def test_safe_mode_raises(
        self, tmp_path: Path, get_db_session: sessionmaker[Session]
    ) -> None:
        """Test that safe mode never reports orphans.

        In safe mode the config could not be read, so every camera would look
        like it had been removed.
        """
        vis = _mock_vis([])
        vis.safe_mode = True
        with pytest.raises(OrphanedCameraUnavailableError, match="safe mode"):
            get_orphaned_cameras(vis, _mock_storage(str(tmp_path), get_db_session))

    def test_failed_component_raises(
        self, tmp_path: Path, get_db_session: sessionmaker[Session]
    ) -> None:
        """Test that a component that failed to set up blocks the listing.

        The cameras of a component that never loaded are not in the domain
        registry, so they would be indistinguishable from removed cameras.
        """
        vis = _mock_vis([])
        vis.data[FAILED] = {"ffmpeg": MagicMock()}
        with pytest.raises(OrphanedCameraUnavailableError, match="ffmpeg"):
            get_orphaned_cameras(vis, _mock_storage(str(tmp_path), get_db_session))

    def test_loading_component_raises(
        self, tmp_path: Path, get_db_session: sessionmaker[Session]
    ) -> None:
        """Test that a component that is still setting up blocks the listing."""
        vis = _mock_vis([])
        vis.data[LOADING] = {"ffmpeg": MagicMock()}
        with pytest.raises(OrphanedCameraUnavailableError, match="still setting up"):
            get_orphaned_cameras(vis, _mock_storage(str(tmp_path), get_db_session))

    def test_skips_unexpected_directory_names(
        self, tmp_path: Path, get_db_session: sessionmaker[Session]
    ) -> None:
        """Test that directories that are not valid identifiers are skipped."""
        tier_path = str(tmp_path)
        _write_file(os.path.join(tier_path, "segments/not a camera/file.m4s"))

        orphaned = get_orphaned_cameras(
            _mock_vis([]), _mock_storage(tier_path, get_db_session)
        )
        assert orphaned == []


class TestDeleteOrphanedCamera:
    """Test delete_orphaned_camera."""

    def test_deletes_files_and_rows(
        self, tmp_path: Path, get_db_session: sessionmaker[Session]
    ) -> None:
        """Test that files and database rows of an orphan are removed."""
        tier_path = str(tmp_path)
        orphan_dir = os.path.join(tier_path, "segments/camera_3")
        keep_dir = os.path.join(tier_path, "segments/camera_1")
        orphan_file = os.path.join(orphan_dir, "file.m4s")
        keep_file = os.path.join(keep_dir, "file.m4s")
        _write_file(orphan_file)
        _write_file(keep_file)

        with get_db_session() as session:
            _add_file(session, tier_path, "camera_3", orphan_file)
            _add_file(session, tier_path, "camera_1", keep_file)
            motion = Motion(
                camera_identifier="camera_3",
                start_time=utcnow(),
                snapshot_path=orphan_file,
            )
            session.add(motion)
            session.flush()
            session.add(MotionContours(motion_id=motion.id, contour=b"0"))
            session.add(
                Objects(
                    camera_identifier="camera_3",
                    label="person",
                    confidence=1.0,
                    width=1.0,
                    height=1.0,
                    x1=0.0,
                    y1=0.0,
                    x2=1.0,
                    y2=1.0,
                    snapshot_path=orphan_file,
                )
            )
            session.add(
                PostProcessorResults(
                    camera_identifier="camera_3",
                    domain="face_recognition",
                    snapshot_path=orphan_file,
                    data={},
                )
            )
            session.add(
                Recordings(
                    camera_identifier="camera_3",
                    start_time=utcnow(),
                    adjusted_start_time=utcnow(),
                )
            )
            session.commit()

        deleted = delete_orphaned_camera(
            _mock_vis(["camera_1"]),
            _mock_storage(tier_path, get_db_session),
            "camera_3",
        )

        assert deleted.camera_identifier == "camera_3"
        assert deleted.file_count == 1
        assert not os.path.exists(orphan_dir)
        assert os.path.exists(keep_file)

        with get_db_session() as session:
            for table in (Files, Motion, Objects, PostProcessorResults, Recordings):
                assert (
                    session.execute(
                        select(table).where(table.camera_identifier == "camera_3")
                    ).first()
                    is None
                )
            assert session.execute(select(MotionContours)).first() is None
            assert (
                session.execute(
                    select(Files).where(Files.camera_identifier == "camera_1")
                ).first()
                is not None
            )

    def test_refuses_configured_camera(
        self, tmp_path: Path, get_db_session: sessionmaker[Session]
    ) -> None:
        """Test that a camera that is still configured is never deleted."""
        tier_path = str(tmp_path)
        keep_file = os.path.join(tier_path, "segments/camera_1/file.m4s")
        _write_file(keep_file)

        with pytest.raises(OrphanedCameraError, match="still configured"):
            delete_orphaned_camera(
                _mock_vis(["camera_1"]),
                _mock_storage(tier_path, get_db_session),
                "camera_1",
            )
        assert os.path.exists(keep_file)

    @pytest.mark.parametrize(
        "camera_identifier", ["../../etc", "camera 3", "camera-3", "", ".."]
    )
    def test_refuses_invalid_identifier(
        self,
        camera_identifier: str,
        tmp_path: Path,
        get_db_session: sessionmaker[Session],
    ) -> None:
        """Test that an identifier that is not a slug is rejected."""
        with pytest.raises(OrphanedCameraError, match="Invalid camera identifier"):
            delete_orphaned_camera(
                _mock_vis([]),
                _mock_storage(str(tmp_path), get_db_session),
                camera_identifier,
            )

    def test_refuses_in_safe_mode(
        self, tmp_path: Path, get_db_session: sessionmaker[Session]
    ) -> None:
        """Test that nothing is deleted while running in safe mode."""
        tier_path = str(tmp_path)
        keep_file = os.path.join(tier_path, "segments/camera_3/file.m4s")
        _write_file(keep_file)

        vis = _mock_vis([])
        vis.safe_mode = True
        with pytest.raises(OrphanedCameraUnavailableError, match="safe mode"):
            delete_orphaned_camera(
                vis, _mock_storage(tier_path, get_db_session), "camera_3"
            )
        assert os.path.exists(keep_file)

    def test_refuses_when_a_component_failed(
        self, tmp_path: Path, get_db_session: sessionmaker[Session]
    ) -> None:
        """Test that nothing is deleted while a component is broken."""
        tier_path = str(tmp_path)
        keep_file = os.path.join(tier_path, "segments/camera_3/file.m4s")
        _write_file(keep_file)

        vis = _mock_vis([])
        vis.data[FAILED] = {"ffmpeg": MagicMock()}
        with pytest.raises(OrphanedCameraUnavailableError, match="ffmpeg"):
            delete_orphaned_camera(
                vis, _mock_storage(tier_path, get_db_session), "camera_3"
            )
        assert os.path.exists(keep_file)

    def test_camera_domain_is_queried(
        self, tmp_path: Path, get_db_session: sessionmaker[Session]
    ) -> None:
        """Test that the configured cameras are read from the camera domain."""
        vis = _mock_vis([])
        delete_orphaned_camera(
            vis, _mock_storage(str(tmp_path), get_db_session), "camera_3"
        )
        vis.domain_registry.get_identifiers.assert_called_with(CAMERA_DOMAIN)
