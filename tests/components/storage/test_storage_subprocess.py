"""Test storage subprocess helpers."""

from queue import Empty

import pytest

from viseron.components.storage.storage_subprocess import (
    DataItemDeleteFile,
    DataItemMoveFile,
    DedupFileQueue,
    FileOperation,
    FileOperationKey,
    file_operation_key,
)


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
    move = DataItemMoveFile(cmd="move_file", src="/src", dst="/dst")
    delete = DataItemDeleteFile(cmd="delete_file", src="/src")

    queue.put(move)
    queue.put(delete)

    assert queue.qsize() == 2
    assert queue.get_nowait() is move
    assert queue.get_nowait() is delete
