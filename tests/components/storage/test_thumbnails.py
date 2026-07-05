"""Tests for thumbnail recovery helpers."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from viseron.components.storage.thumbnails import (
    RecoveredThumbnail,
    recover_recording_thumbnail,
)
from viseron.domains.camera.fragmenter import Fragment


def test_recover_recording_thumbnail_registers_existing_thumbnail(
    tmp_path: Path,
) -> None:
    """An existing thumbnail is registered as a Files row."""
    thumbnail_path = tmp_path / "1.jpg"
    thumbnail_path.write_bytes(b"jpg")
    camera = MagicMock(identifier="test", thumbnails_folder=str(tmp_path))
    storage = MagicMock()

    with patch(
        "viseron.components.storage.thumbnails._set_recording_thumbnail_path"
    ) as mock_set_path, patch(
        "viseron.components.storage.thumbnails.upsert_thumbnail_file",
        return_value=12,
    ) as mock_upsert:
        recovered_thumbnail = recover_recording_thumbnail(
            storage,
            camera,
            1,
            str(thumbnail_path),
            10,
        )

    assert recovered_thumbnail == RecoveredThumbnail(
        path=str(thumbnail_path), file_id=12
    )
    mock_upsert.assert_called_once_with(
        storage.get_session, storage, camera.identifier, str(thumbnail_path)
    )
    mock_set_path.assert_called_once_with(
        storage.get_session, 1, str(thumbnail_path), 12
    )


def test_recover_recording_thumbnail_extracts_from_fragments(
    tmp_path: Path,
) -> None:
    """A missing thumbnail is extracted from the first usable fragment."""
    camera = MagicMock(identifier="test", thumbnails_folder=str(tmp_path))
    storage = MagicMock()
    fragment_time = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    fragment_file = MagicMock(
        filename="1.m4s",
        path="/segments/test/1.m4s",
        duration=5.0,
        orig_ctime=fragment_time,
    )
    expected_path = str(tmp_path / "1.jpg")

    with patch(
        "viseron.components.storage.thumbnails.get_recording_fragments",
        return_value=[fragment_file],
    ) as mock_get_fragments, patch(
        "viseron.components.storage.thumbnails._extract_thumbnail_from_fragment",
        return_value=True,
    ) as mock_extract, patch(
        "viseron.components.storage.thumbnails._set_recording_thumbnail_path"
    ) as mock_set_path, patch(
        "viseron.components.storage.thumbnails.upsert_thumbnail_file",
        return_value=13,
    ) as mock_upsert:
        recovered_thumbnail = recover_recording_thumbnail(
            storage,
            camera,
            1,
            None,
            10,
        )

    assert recovered_thumbnail == RecoveredThumbnail(path=expected_path, file_id=13)
    mock_get_fragments.assert_called_once_with(1, 10, storage.get_session)
    mock_extract.assert_called_once_with(
        camera,
        Fragment("1.m4s", "/segments/test/1.m4s", 5.0, fragment_time),
        expected_path,
    )
    mock_upsert.assert_called_once_with(
        storage.get_session, storage, camera.identifier, expected_path
    )
    mock_set_path.assert_called_once_with(storage.get_session, 1, expected_path, 13)
