"""Tests for viseron.helpers.child_process_worker."""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import pickle
import queue
from contextlib import ExitStack
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from viseron.helpers.child_process_worker import (
    LOGGER,
    ChildProcessWork,
    ChildProcessWorker,
    ChildProcessWorkerConfig,
    run_child_process_worker,
)
from viseron.watchdog.process_watchdog import ProcessWatchDog
from viseron.watchdog.thread_watchdog import ThreadWatchDog

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from tests.conftest import MockViseron

CONFIG = ChildProcessWorkerConfig(
    name="viseron.child_process.test.process",
    sensitive_strings=("hunter2",),
    log_level=logging.INFO,
)


class _PidWork(ChildProcessWork):
    """Tag every item with the pid of the process that handled it."""

    def __init__(self) -> None:
        self._initialized_in: int | None = None

    def initialize(self) -> None:
        """Remember the process the work was initialized in."""
        self._initialized_in = os.getpid()

    def work_input(self, item: Any) -> dict[str, Any]:
        """Return the item along with where it was handled."""
        return {
            "item": item,
            "pid": os.getpid(),
            "initialized_in": self._initialized_in,
        }


class _Worker(ChildProcessWorker):
    """Collect the output of the child process."""

    def __init__(self, vis: MockViseron) -> None:
        self.results: queue.Queue[dict[str, Any]] = queue.Queue()
        super().__init__(vis, "test", _PidWork())

    def work_output(self, item: dict[str, Any]) -> None:
        """Store the output of the child process."""
        self.results.put(item)


class _LegacyWorker(ChildProcessWorker):
    """Worker that performs the work itself instead of handing over a work."""

    def __init__(self, vis: MockViseron) -> None:
        self.results: queue.Queue[dict[str, Any]] = queue.Queue()
        self._initialized_in: int | None = None
        super().__init__(vis, "legacy_test")

    def process_initialization(self) -> None:
        """Remember the process the worker was initialized in."""
        self._initialized_in = os.getpid()

    def work_input(self, item: Any) -> dict[str, Any]:
        """Return the item along with where it was handled."""
        return {
            "item": item,
            "pid": os.getpid(),
            "initialized_in": self._initialized_in,
        }

    def work_output(self, item: dict[str, Any]) -> None:
        """Store the output of the child process."""
        self.results.put(item)


@pytest.fixture(
    name="worker",
    params=[
        pytest.param(_Worker, id="work"),
        pytest.param(_LegacyWorker, id="legacy"),
    ],
)
def fixture_worker(
    request: pytest.FixtureRequest, vis: MockViseron
) -> Iterator[_Worker | _LegacyWorker]:
    """Return a started worker, stopping it afterwards."""
    registered_processes = ProcessWatchDog.registered_items[:]
    registered_threads = ThreadWatchDog.registered_items[:]
    worker = request.param(vis)
    try:
        yield worker
    finally:
        worker.stop()
        ProcessWatchDog.registered_items[:] = registered_processes
        ThreadWatchDog.registered_items[:] = registered_threads


def test_config_is_picklable() -> None:
    """The config crosses a forkserver boundary, so it must pickle."""
    assert pickle.loads(pickle.dumps(CONFIG)) == CONFIG  # noqa: S301


def test_run_child_process_worker_output_queue() -> None:
    """Work is initialized before any input and every result is put on the queue."""
    exit_event = MagicMock()
    exit_event.is_set.side_effect = [False, False, True]
    process_queue: queue.Queue[int] = queue.Queue()
    process_queue.put(1)
    process_queue.put(2)
    output_queue: queue.Queue[dict[str, Any]] = queue.Queue()
    work = _PidWork()

    with ExitStack() as stack:
        module = "viseron.helpers.child_process_worker"
        stack.enter_context(patch(f"{module}.remove_shm_from_resource_tracker"))
        stack.enter_context(patch(f"{module}.setproctitle"))
        stack.enter_context(patch(f"{module}.enable_child_logging"))
        run_child_process_worker(
            CONFIG,
            work,
            exit_event,
            process_queue,  # type: ignore[arg-type]
            output_queue,  # type: ignore[arg-type]
        )

    assert work.output_queue is output_queue
    assert output_queue.get_nowait() == {
        "item": 1,
        "pid": os.getpid(),
        "initialized_in": os.getpid(),
    }
    assert output_queue.get_nowait()["item"] == 2


def test_work_runs_in_a_child(worker: _Worker | _LegacyWorker) -> None:
    """Input reaches the work in the child process and the output comes back."""
    worker.input_queue.put("item")

    result = worker.results.get(timeout=120)

    assert result["item"] == "item"
    assert result["pid"] != os.getpid()
    assert result["initialized_in"] == result["pid"]


@pytest.mark.parametrize("worker", [_Worker], indirect=True)
def test_work_runs_in_a_forkserver_child(worker: _Worker) -> None:
    """Work is handed over to a child created with forkserver."""
    assert worker._process_frames_proc._ctx.get_start_method() == "forkserver"


@pytest.mark.parametrize("worker", [_Worker], indirect=True)
def test_child_follows_the_log_levels(worker: _Worker) -> None:
    """A forkserver child doesn't inherit the parent's loggers."""
    child_log_levels = worker._process_frames_proc._child_log_levels

    assert child_log_levels is not None
    assert child_log_levels._logger_names == (LOGGER.name, _PidWork.__module__)


def test_restarted_child_gets_new_queues(worker: _Worker | _LegacyWorker) -> None:
    """A killed child can leave its queues locked, so a restart must replace them."""
    worker.input_queue.put("before")
    before = worker.results.get(timeout=120)
    process_queue = worker._process_queue

    worker._process_frames_proc.restart(timeout=5)
    worker.input_queue.put("after")
    after = worker.results.get(timeout=120)

    assert worker._process_queue is not process_queue
    assert after["item"] == "after"
    assert after["pid"] != before["pid"]


def test_work_and_mp_context_are_mutually_exclusive(vis: MockViseron) -> None:
    """The child process context of a worker with work can't be overridden."""
    with pytest.raises(ValueError, match="mp_context"):
        ChildProcessWorker.__init__(
            MagicMock(), vis, "test", _PidWork(), mp_context=mp.get_context()
        )


class _WorkerWithoutWorkInput(ChildProcessWorker):
    """Worker that neither hands over work nor performs it itself."""

    def work_output(self, item: Any) -> None:
        """Discard the output of the child process."""


class _WorkerWithWorkAndWorkInput(_Worker):
    """Worker that both hands over work and performs it itself."""

    def work_input(self, item: Any) -> Any:
        """Never called, since the work is performed by the work."""
        return item


@pytest.mark.parametrize(
    "create_worker",
    [
        pytest.param(
            lambda vis: _WorkerWithoutWorkInput(vis, "test"), id="no_work_input"
        ),
        pytest.param(_WorkerWithWorkAndWorkInput, id="work_and_work_input"),
    ],
)
def test_worker_needs_exactly_one_work_input(
    vis: MockViseron, create_worker: Callable[[MockViseron], ChildProcessWorker]
) -> None:
    """Without work_input every item fails, and with two one is silently ignored."""
    with pytest.raises(TypeError, match="work_input"):
        create_worker(vis)
