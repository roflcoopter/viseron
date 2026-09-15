"""Tests for the process watchdog."""

from __future__ import annotations

import gc
import logging
import multiprocessing as mp
import os
import pickle
import subprocess as sp
import time
from typing import TYPE_CHECKING

import psutil
import pytest

from viseron.helpers.logs import (
    refresh_child_log_levels,
    unregister_child_log_levels,
)
from viseron.watchdog.process_watchdog import (
    RestartableProcess,
    _ChildProcessTarget,
)

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


def _report_child_setup(queue) -> None:
    """Run in the child; report what the target wrapper set up."""
    queue.put(
        {
            "session_leader": os.getsid(0) == os.getpid(),
            "frozen_objects": gc.get_freeze_count(),
        }
    )


class TestChildProcessTarget:
    """Tests for the picklable wrapper used as the child process entrypoint."""

    def test_is_picklable(self) -> None:
        """The wrapper must survive pickling; forkserver pickles the target."""
        restored = pickle.loads(  # noqa: S301
            pickle.dumps(_ChildProcessTarget(_report_child_setup, False))
        )
        assert restored._target is _report_child_setup
        assert restored._start_watchdogs is False

    def test_defaults_to_current_context(self) -> None:
        """Passing no context must not change existing behaviour."""
        process = RestartableProcess(
            target=_report_child_setup, name="ctx_default", register=False
        )
        assert process._ctx.get_start_method() == mp.get_start_method()

    def test_forkserver_child_is_session_leader_and_frozen(self) -> None:
        """The wrapper calls os.setsid() and gc.freeze() inside the child.

        os.setsid() is what _signal_process_group relies on to reach the
        subprocesses the child started.
        """
        ctx = mp.get_context("forkserver")
        queue = ctx.Queue()
        process = RestartableProcess(
            target=_report_child_setup,
            args=(queue,),
            name="forkserver_child",
            register=False,
            context="forkserver",
        )
        process.start()
        try:
            result = queue.get(timeout=120)
        finally:
            process.join(timeout=30)
            process.kill()

        assert result["session_leader"] is True
        assert result["frozen_objects"] > 0


CHILD_LOGGER = "test_child_logger"


def _report_log_levels(queue) -> None:
    """Run in the child; report the level of the logger the parent named."""
    queue.put(logging.getLogger(CHILD_LOGGER).level)
    deadline = time.time() + 30
    while (
        logging.getLogger(CHILD_LOGGER).level != logging.DEBUG
        and time.time() < deadline
    ):
        time.sleep(0.01)
    queue.put(logging.getLogger(CHILD_LOGGER).level)


def _wait_forever() -> None:
    """Run in the child; stay alive until the parent stops it."""
    while True:
        time.sleep(0.1)


class TestChildLogLevels:
    """Tests for the log levels a process shares with its child."""

    @pytest.fixture(autouse=True)
    def _child_logger(self) -> Iterator[None]:
        """Remove the logger the shared levels are created for."""
        try:
            yield
        finally:
            logging.Logger.manager.loggerDict.pop(CHILD_LOGGER, None)

    def test_child_follows_the_levels_of_the_logger_names_it_was_given(self) -> None:
        """A child applies its levels on startup and follows every change."""
        logging.getLogger(CHILD_LOGGER).setLevel(logging.INFO)
        ctx = mp.get_context("forkserver")
        queue = ctx.Queue()
        process = RestartableProcess(
            target=_report_log_levels,
            args=(queue,),
            name="log_levels_child",
            register=False,
            context="forkserver",
            child_logger_names=(CHILD_LOGGER,),
        )

        process.start()
        try:
            assert queue.get(timeout=120) == logging.INFO

            logging.getLogger(CHILD_LOGGER).setLevel(logging.DEBUG)
            refresh_child_log_levels()

            assert queue.get(timeout=120) == logging.DEBUG
        finally:
            process.join(timeout=30)
            process.kill()
            unregister_child_log_levels("log_levels_child")
            del logging.Logger.manager.loggerDict[CHILD_LOGGER]

    @pytest.mark.parametrize("stop_method", ["stop", "terminate", "kill"])
    def test_stopping_the_process_unregisters_its_log_levels(
        self, stop_method: str
    ) -> None:
        """The levels of a process that is gone must not be refreshed any more."""
        process = RestartableProcess(
            target=_wait_forever,
            name="log_levels_stop",
            register=False,
            child_logger_names=(CHILD_LOGGER,),
        )
        child_log_levels = process._child_log_levels

        getattr(process, stop_method)()
        refresh_child_log_levels()

        assert child_log_levels.wait_and_apply(timeout=0.01) is False

    def test_restarting_the_process_keeps_its_log_levels_registered(self) -> None:
        """A restarted child must keep following the levels it was given."""
        process = RestartableProcess(
            target=_wait_forever,
            name="log_levels_restart",
            register=False,
            child_logger_names=(CHILD_LOGGER,),
        )
        child_log_levels = process._child_log_levels
        process.start()

        try:
            process.restart(timeout=10)
            refresh_child_log_levels()

            assert child_log_levels.wait_and_apply(timeout=5) is True
        finally:
            process.kill()
            unregister_child_log_levels("log_levels_restart")

    def test_child_logger_names_require_a_process_name(self) -> None:
        """The name keys the shared levels, so it cannot be left out."""
        with pytest.raises(ValueError, match="name"):
            RestartableProcess(
                target=_wait_forever,
                register=False,
                child_logger_names=(CHILD_LOGGER,),
            )

    def test_child_logger_names_need_the_wrapped_target(self) -> None:
        """A process that is not wrapped cannot apply the levels in the child."""
        with pytest.raises(ValueError, match="create_process_method"):
            RestartableProcess(
                name="log_levels_unwrapped",
                register=False,
                create_process_method=lambda: mp.Process(target=_wait_forever),
                child_logger_names=(CHILD_LOGGER,),
            )
