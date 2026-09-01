"""Tests for viseron.helpers.child_process_context."""

from __future__ import annotations

import os

from viseron.helpers.child_process_context import (
    CHILD_PROCESS_START_METHOD,
    get_child_process_context,
)

# Appended to in the parent after import. A forkserver child re-imports this module
# from scratch, so it must still be empty there. If someone reverts the start method
# to fork, the child inherits the parent's value and this test will fail.
MARKER: list[str] = []


def _report(queue) -> None:
    queue.put((list(MARKER), os.getpid()))


def test_start_method_is_forkserver() -> None:
    """The whole change hinges on not using fork."""
    assert CHILD_PROCESS_START_METHOD == "forkserver"
    assert get_child_process_context().get_start_method() == "forkserver"


def test_context_is_a_singleton() -> None:
    """Multiprocessing caches concrete contexts; preload must only be set once."""
    assert get_child_process_context() is get_child_process_context()


def test_child_does_not_inherit_parent_memory() -> None:
    """The regression test for the whole change.

    A fork child would see MARKER == ["set in parent"]. A forkserver child imports
    this module fresh from the forkserver snapshot and must see an empty list.
    """
    ctx = get_child_process_context()
    queue = ctx.Queue()
    MARKER.append("set in parent")
    try:
        process = ctx.Process(target=_report, args=(queue,))
        process.start()
        try:
            marker, child_pid = queue.get(timeout=120)
        finally:
            process.join(timeout=30)
        assert marker == []
        assert child_pid != os.getpid()
    finally:
        MARKER.clear()
