"""Tests for the process watchdog."""

from __future__ import annotations

import multiprocessing as mp
import subprocess as sp
import time
from typing import TYPE_CHECKING

import psutil
import pytest

from viseron.watchdog.process_watchdog import RestartableProcess

if TYPE_CHECKING:
    from collections.abc import Iterator

GRANDCHILD_COMMAND = ["sleep", "60"]


def _spawn_grandchild(pid_queue: mp.Queue) -> None:
    """Start a subprocess and block, like the ffmpeg frame reader does."""
    process = sp.Popen(GRANDCHILD_COMMAND)  # noqa: S603
    pid_queue.put(process.pid)
    while True:
        time.sleep(0.1)


def _create_process(pid_queue: mp.Queue) -> mp.Process:
    """Return a process that does not get wrapped with os.setsid."""
    return mp.Process(target=_spawn_grandchild, args=(pid_queue,), daemon=True)


def _alive(pid: int) -> bool:
    """Return True while the process exists and has not been reaped."""
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def _wait_until_dead(pid: int, timeout: float = 10) -> bool:
    """Wait for a pid to disappear, returning False on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.05)
    return False


def _kill(pid: int) -> None:
    """Kill a leftover process so a failing test does not leak it."""
    try:
        psutil.Process(pid).kill()
    except psutil.NoSuchProcess:
        pass


@pytest.fixture(name="frame_reader")
def fixture_frame_reader() -> Iterator[tuple[RestartableProcess, int]]:
    """Return a started process along with the pid of the subprocess it spawned."""
    pid_queue: mp.Queue = mp.Queue()
    process = RestartableProcess(
        name="test_frame_reader",
        target=_spawn_grandchild,
        args=(pid_queue,),
        daemon=True,
        register=False,
    )
    process.start()
    grandchild_pid = pid_queue.get(timeout=30)
    yield process, grandchild_pid
    _kill(grandchild_pid)
    process.kill()


class TestProcessGroupCleanup:
    """Tests that stopping a process does not orphan the processes it started.

    The ffmpeg frame reader starts its ffmpeg subprocesses from inside the child
    process, so the parent has no handle on them. Killing only the child leaves
    ffmpeg running forever.
    """

    def test_kill_kills_the_subprocesses_the_child_started(
        self, frame_reader: tuple[RestartableProcess, int]
    ) -> None:
        """kill() takes the whole process group with it."""
        process, grandchild_pid = frame_reader
        assert _alive(grandchild_pid)

        process.kill()

        assert _wait_until_dead(grandchild_pid)

    def test_terminate_kills_the_subprocesses_the_child_started(
        self, frame_reader: tuple[RestartableProcess, int]
    ) -> None:
        """terminate() takes the whole process group with it."""
        process, grandchild_pid = frame_reader
        assert _alive(grandchild_pid)

        process.terminate()

        assert _wait_until_dead(grandchild_pid)

    def test_restart_kills_the_subprocesses_the_old_child_started(
        self, frame_reader: tuple[RestartableProcess, int]
    ) -> None:
        """The watchdog restart path does not leave the old subprocesses behind."""
        process, grandchild_pid = frame_reader
        assert _alive(grandchild_pid)

        process.restart(timeout=5)

        assert _wait_until_dead(grandchild_pid)

    def test_kill_does_not_signal_a_process_group_the_child_did_not_create(
        self,
    ) -> None:
        """A process built by create_process_method never calls os.setsid.

        It therefore shares Viseron's process group, and signalling that group
        would take down Viseron itself.
        """
        pid_queue: mp.Queue = mp.Queue()
        sibling = sp.Popen(GRANDCHILD_COMMAND)  # noqa: S603
        process = RestartableProcess(
            name="test_shared_group",
            create_process_method=lambda: _create_process(pid_queue),
            register=False,
        )
        process.start()
        grandchild_pid = pid_queue.get(timeout=30)

        process.kill()

        try:
            assert _alive(sibling.pid)
        finally:
            _kill(grandchild_pid)
            _kill(sibling.pid)
