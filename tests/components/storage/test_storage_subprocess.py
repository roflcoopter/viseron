"""Test storage subprocess helpers."""

import datetime
import itertools
import threading
from collections import OrderedDict
from queue import Empty
from unittest.mock import MagicMock

import pytest

from viseron.components.storage.storage_subprocess import (
    DataItem,
    DataItemCopyFile,
    DataItemDeleteFile,
    DataItemMoveFile,
    DedupFileQueue,
    FileOperation,
    FileOperationKey,
    TierCheckWorker,
    file_operation_key,
)


class FakeQueue:
    """Queue fake that records inserted items."""

    def __init__(self) -> None:
        self.items = []

    def put(self, item):
        """Record item."""
        self.items.append(item)


def make_tier_check_worker() -> TierCheckWorker:
    """Create a TierCheckWorker without spawning its subprocess."""
    worker = TierCheckWorker.__new__(TierCheckWorker)
    worker._callbacks = OrderedDict()
    worker._callbacks_lock = threading.Lock()
    worker._next_callback_id = itertools.count(1)
    worker._latest_deduped_callbacks = {}
    worker._deduped_callback_keys = {}
    worker.input_queue = FakeQueue()
    return worker


def make_data_item(**kwargs) -> DataItem:
    """Create a check_tier DataItem."""
    defaults = {
        "cmd": "check_tier",
        "camera_identifier": "test",
        "tier_id": 0,
        "category": "recorder",
        "subcategories": ["segments"],
        "throttle_period": datetime.timedelta(minutes=1),
        "max_bytes": 0,
        "min_age": datetime.timedelta(seconds=0),
        "max_age": datetime.timedelta(seconds=0),
        "min_bytes": 0,
        "drain": False,
    }
    defaults.update(kwargs)
    return DataItem(**defaults)


def test_dedup_file_queue_replaces_identical_queued_jobs() -> None:
    """Identical queued file operations should collapse to the latest job."""
    queue = DedupFileQueue[FileOperation, FileOperationKey](file_operation_key)
    first = DataItemMoveFile(cmd="move_file", src="/src", dst="/dst", callback_id="1")
    second = DataItemMoveFile(cmd="move_file", src="/src", dst="/dst", callback_id="2")

    queue.put(first)
    queue.put(second)

    assert queue.qsize() == 1
    assert queue.get_nowait() is second
    with pytest.raises(Empty):
        queue.get_nowait()


def test_dedup_file_queue_keeps_distinct_operations() -> None:
    """Different file operations should remain queued independently."""
    queue = DedupFileQueue[FileOperation, FileOperationKey](file_operation_key)
    copy = DataItemCopyFile(cmd="copy_file", src="/src", dst="/dst")
    move = DataItemMoveFile(cmd="move_file", src="/src", dst="/dst")
    delete = DataItemDeleteFile(cmd="delete_file", src="/src")

    queue.put(copy)
    queue.put(move)
    queue.put(delete)

    assert queue.qsize() == 3
    assert queue.get_nowait() is copy
    assert queue.get_nowait() is move
    assert queue.get_nowait() is delete


def test_dedup_file_queue_keeps_callback_copy_jobs_distinct() -> None:
    """Copy callbacks can gate different moves and must not collapse."""
    queue = DedupFileQueue[FileOperation, FileOperationKey](file_operation_key)
    first = DataItemCopyFile(cmd="copy_file", src="/src", dst="/dst", callback_id="1")
    second = DataItemCopyFile(cmd="copy_file", src="/src", dst="/dst", callback_id="2")

    queue.put(first)
    queue.put(second)

    assert queue.qsize() == 2
    assert queue.get_nowait() is first
    assert queue.get_nowait() is second


def test_tier_check_worker_replaces_superseded_check_tier_callback() -> None:
    """Parent callback tracking should mirror check_tier queue dedupe."""
    worker = make_tier_check_worker()
    first_callback = MagicMock()
    second_callback = MagicMock()
    first = make_data_item()
    second = make_data_item()

    worker.send_command(first, first_callback)
    worker.send_command(second, second_callback)

    assert first.callback_id == "1"
    assert second.callback_id == "2"
    assert list(worker._callbacks) == ["2"]
    assert worker.input_queue.items == [first, second]

    worker.work_output(first)
    first_callback.assert_not_called()

    worker.work_output(second)
    second_callback.assert_called_once_with(second)
    assert worker._callbacks == {}
    assert worker._latest_deduped_callbacks == {}
    assert worker._deduped_callback_keys == {}


def test_tier_check_worker_keeps_distinct_check_tier_callbacks() -> None:
    """Different check_tier throttle keys should keep independent callbacks."""
    worker = make_tier_check_worker()
    first_callback = MagicMock()
    second_callback = MagicMock()
    first = make_data_item(subcategories=["segments"])
    second = make_data_item(subcategories=["recordings"])

    worker.send_command(first, first_callback)
    worker.send_command(second, second_callback)

    assert list(worker._callbacks) == ["1", "2"]

    worker.work_output(first)
    worker.work_output(second)

    first_callback.assert_called_once_with(first)
    second_callback.assert_called_once_with(second)


def test_tier_check_worker_replaces_superseded_move_file_callback() -> None:
    """Parent callback tracking should mirror move_file queue dedupe."""
    worker = make_tier_check_worker()
    first_callback = MagicMock()
    second_callback = MagicMock()
    first = DataItemMoveFile(cmd="move_file", src="/src", dst="/dst")
    second = DataItemMoveFile(cmd="move_file", src="/src", dst="/dst")

    worker.send_command(first, first_callback)
    worker.send_command(second, second_callback)

    assert list(worker._callbacks) == ["2"]

    worker.work_output(first)
    first_callback.assert_not_called()

    worker.work_output(second)
    second_callback.assert_called_once_with(second)
