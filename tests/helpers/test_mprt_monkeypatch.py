"""Tests for viseron.helpers.mprt_monkeypatch."""

from multiprocessing import resource_tracker
from unittest.mock import MagicMock, patch

from viseron.helpers.mprt_monkeypatch import remove_shm_from_resource_tracker


def test_register_passthrough_non_shared_memory():
    """Non-shared-memory resources must reach the real tracker untouched.

    The patched register used to pass a stray `self` as the name and an extra
    positional argument, raising NameError for any rtype other than
    shared_memory.
    """
    remove_shm_from_resource_tracker()
    mock_tracker = MagicMock()
    with patch.object(resource_tracker, "_resource_tracker", mock_tracker):
        resource_tracker.register("shm_name", "semaphore")
    mock_tracker.register.assert_called_once_with("shm_name", "semaphore")


def test_unregister_passthrough_non_shared_memory():
    """Non-shared-memory resources must reach the real tracker untouched."""
    remove_shm_from_resource_tracker()
    mock_tracker = MagicMock()
    with patch.object(resource_tracker, "_resource_tracker", mock_tracker):
        resource_tracker.unregister("shm_name", "semaphore")
    mock_tracker.unregister.assert_called_once_with("shm_name", "semaphore")


def test_shared_memory_is_still_skipped():
    """Shared memory remains excluded from tracking."""
    remove_shm_from_resource_tracker()
    mock_tracker = MagicMock()
    with patch.object(resource_tracker, "_resource_tracker", mock_tracker):
        resource_tracker.register("shm_name", "shared_memory")
    mock_tracker.register.assert_not_called()
