"""Tests for viseron.helpers.storage."""

import json
import logging

import pytest

import viseron.helpers.storage as storage_module
from viseron.helpers.storage import Storage, StorageReadError


@pytest.fixture(name="storage_path")
def storage_path_fixture(tmp_path, monkeypatch):
    """Point STORAGE_PATH at a temporary directory."""
    monkeypatch.setattr(storage_module, "STORAGE_PATH", str(tmp_path))
    return tmp_path


@pytest.fixture(name="fake_vis")
def fake_vis_fixture():
    """Return a dummy Viseron replacement."""

    class _FakeVis:
        """Minimal stand-in for Viseron."""

    return _FakeVis()


def _write(storage_path, name, content: str):
    path = storage_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_save_and_load_roundtrip(storage_path, fake_vis):
    """Saved data loads back unchanged."""
    store = Storage(fake_vis, "roundtrip.json", version=2)
    store.save({"camera": {"expire_after": 5}})
    assert (storage_path / "roundtrip.json").exists()
    loaded = Storage(fake_vis, "roundtrip.json", version=2).load()
    assert loaded == {"camera": {"expire_after": 5}}


def test_load_missing_file_returns_empty_dict(storage_path, fake_vis):
    """A missing storage file yields an empty dict."""
    store = Storage(fake_vis, "does_not_exist.json")
    assert store.path.startswith(str(storage_path))
    assert store.load() == {}


def test_load_corrupt_json_raises_storage_read_error(storage_path, fake_vis):
    """A truncated/corrupt file raises StorageReadError, not JSONDecodeError.

    StorageReadError lets callers like safe mode and auth setup treat the
    file as unreadable; a raw JSONDecodeError (a ValueError) escapes the
    existing OSError handling and crashes setup instead.
    """
    _write(storage_path, "corrupt.json", '{"version": 1, "data":')
    store = Storage(fake_vis, "corrupt.json")
    with pytest.raises(StorageReadError):
        store.load()


def test_load_non_dict_json_raises_storage_read_error(storage_path, fake_vis):
    """A JSON body that is not an object raises StorageReadError."""
    _write(storage_path, "alist.json", json.dumps([1, 2, 3]))
    store = Storage(fake_vis, "alist.json")
    with pytest.raises(StorageReadError):
        store.load()


def test_load_missing_version_returns_data(storage_path, fake_vis, caplog):
    """A file without a version key still returns its data, with a warning."""
    _write(storage_path, "noversion.json", json.dumps({"data": {"a": 1}}))
    store = Storage(fake_vis, "noversion.json")
    with caplog.at_level(logging.WARNING, logger="viseron.helpers.storage"):
        assert store.load() == {"a": 1}
    assert any("version mismatch" in record.message for record in caplog.records)


def test_load_version_mismatch_warns(storage_path, fake_vis, caplog):
    """A version mismatch warns but still returns the data."""
    _write(storage_path, "oldversion.json", json.dumps({"version": 1, "data": {}}))
    store = Storage(fake_vis, "oldversion.json", version=2)
    with caplog.at_level(logging.WARNING, logger="viseron.helpers.storage"):
        assert store.load() == {}
    assert any("version mismatch" in record.message for record in caplog.records)
