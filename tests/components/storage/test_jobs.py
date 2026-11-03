"""Tests for viseron.components.storage.jobs."""

from __future__ import annotations

import logging
import os
import pickle
import tempfile
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from apscheduler.triggers.cron import CronTrigger

from viseron.components.storage.jobs import (
    CleanupJobConfig,
    EmptyFoldersCleanup,
    OrphanedDatabaseFilesCleanup,
    OrphanedEventClipsCleanup,
    OrphanedFilesCleanup,
    OrphanedThumbnailsCleanup,
)
from viseron.exceptions import DomainNotRegisteredError
from viseron.viseron_types import SnapshotDomain

if TYPE_CHECKING:
    from collections.abc import Iterator

    from viseron.components.storage.jobs import BaseCleanupJob

ALL_PATHS = [
    "/clips",
    "/segments",
    "/thumbnails",
    "/timelapse",
    *[f"/snapshots/{domain.value}" for domain in SnapshotDomain],
]


def _storage() -> MagicMock:
    """Return a storage that resolves one path per kind of file."""
    storage = MagicMock()
    storage.ignored_files = ["init.mp4"]
    storage.get_event_clips_path.return_value = ["/clips"]
    storage.get_segments_path.return_value = ["/segments"]
    storage.get_thumbnails_path.return_value = ["/thumbnails"]
    storage.get_timelapse_path.return_value = ["/timelapse"]
    storage.get_snapshots_path.side_effect = lambda _camera, domain, **_kwargs: [
        f"/snapshots/{domain.value}"
    ]
    return storage


def _vis() -> MagicMock:
    """Return a Viseron instance with a single camera."""
    vis = MagicMock()
    vis.get_registered_identifiers.return_value = {"camera": MagicMock()}
    return vis


@pytest.fixture(name="storage_dir")
def fixture_storage_dir() -> Iterator[str]:
    """Return a temporary storage directory."""
    with tempfile.TemporaryDirectory() as storage_dir:
        yield storage_dir


def test_config_is_picklable() -> None:
    """The config crosses a forkserver boundary, so it must pickle."""
    config = CleanupJobConfig(
        name="cleanup_test",
        paths=["/clips"],
        ignored_files=frozenset({"init.mp4"}),
        sensitive_strings=("hunter2",),
        log_level=logging.INFO,
    )
    assert pickle.loads(pickle.dumps(config)) == config  # noqa: S301


@pytest.mark.parametrize(
    ("job_class", "expected_paths"),
    [
        pytest.param(OrphanedFilesCleanup, ALL_PATHS, id="orphaned_files"),
        pytest.param(EmptyFoldersCleanup, ALL_PATHS, id="empty_folders"),
        pytest.param(
            OrphanedThumbnailsCleanup, ["/thumbnails"], id="orphaned_thumbnails"
        ),
        pytest.param(OrphanedEventClipsCleanup, ["/clips"], id="orphaned_clips"),
        pytest.param(OrphanedDatabaseFilesCleanup, [], id="orphaned_db_files"),
    ],
)
def test_paths_are_resolved_in_the_parent(
    job_class: type[BaseCleanupJob], expected_paths: list[str]
) -> None:
    """The child can't reach the cameras, so the parent resolves their paths."""
    job = job_class(_vis(), _storage(), CronTrigger(hour=0))
    assert job._get_paths() == expected_paths


def test_no_paths_without_cameras() -> None:
    """Jobs must not fail before any camera has been registered."""
    vis = MagicMock()
    vis.get_registered_identifiers.side_effect = DomainNotRegisteredError("camera")
    job = OrphanedFilesCleanup(vis, _storage(), CronTrigger(hour=0))
    assert job._get_paths() == []


def test_run_executes_the_job_in_a_child_process(storage_dir: str) -> None:
    """The empty folders job needs no database, so the whole round trip can run."""
    empty_folder = os.path.join(storage_dir, "empty")
    os.makedirs(empty_folder)
    kept_folder = os.path.join(storage_dir, "kept")
    os.makedirs(kept_folder)
    with open(os.path.join(kept_folder, "file"), "w", encoding="utf-8") as file:
        file.write("content")
    storage = _storage()
    storage.get_event_clips_path.return_value = [storage_dir]
    storage.get_segments_path.return_value = []
    storage.get_thumbnails_path.return_value = []
    storage.get_timelapse_path.return_value = None
    storage.get_snapshots_path.side_effect = None
    storage.get_snapshots_path.return_value = []
    job = EmptyFoldersCleanup(_vis(), storage, CronTrigger(hour=0))

    job.run()

    assert not os.path.exists(empty_folder)
    assert os.path.exists(kept_folder)
    assert job.running is False
