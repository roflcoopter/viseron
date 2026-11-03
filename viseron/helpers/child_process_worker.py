"""Helper to perform work in a child process.

The child process is created with the forkserver start method to reduce memory usage,
so it does not inherit anything from the running Viseron instance. Everything it needs
is handed over as a picklable ChildProcessWork.

Workers that are not yet migrated to ChildProcessWork implement work_input and
process_initialization on the worker itself instead. The worker is then run in a child
process created from mp_context, the default start method unless given.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

import setproctitle

from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.helpers import pop_if_full
from viseron.helpers.child_process_context import (
    CHILD_PROCESS_START_METHOD,
    get_child_process_context,
)
from viseron.helpers.logs import SensitiveInformationFilter, enable_child_logging
from viseron.helpers.mprt_monkeypatch import remove_shm_from_resource_tracker
from viseron.watchdog.process_watchdog import RestartableProcess
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from multiprocessing.context import BaseContext
    from multiprocessing.synchronize import Event

    from viseron import Viseron


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChildProcessWorkerConfig:
    """Everything the child process needs besides its work.

    It is important that this only contains picklable data.
    """

    name: str
    sensitive_strings: tuple[str, ...]
    log_level: int


class ChildProcessWork(ABC):
    """Work performed inside the child process of a ChildProcessWorker.

    Instances are pickled into the child process, so they may only hold plain data and
    multiprocessing primitives created from the child process context. Anything that
    can't be pickled has to be created in initialize.

    The work is reused when the child process is restarted, so it should not hold
    queues of its own, which a killed child can leave locked. Results are returned
    through output_queue, which the worker recreates on every start.
    """

    output_queue: mp.Queue

    @property
    def logger_names(self) -> tuple[str, ...]:
        """Return the names of the loggers the work uses in the child process."""
        return (type(self).__module__,)

    def initialize(self) -> None:
        """Run initializations inside the child process."""

    @abstractmethod
    def work_input(self, item: Any) -> Any:
        """Perform work on input item in the child process."""


def run_child_process_worker(
    config: ChildProcessWorkerConfig,
    work: ChildProcessWork,
    exit_event: Event,
    process_queue: mp.Queue,
    output_queue: mp.Queue,
) -> None:
    """Entrypoint of the child process."""
    remove_shm_from_resource_tracker()
    setproctitle.setproctitle(config.name)
    enable_child_logging(config.sensitive_strings, config.log_level)
    work.output_queue = output_queue
    work.initialize()

    while not exit_event.is_set():
        try:
            item = process_queue.get(timeout=1)
        except Empty:
            continue
        processed_item = work.work_input(item)
        pop_if_full(output_queue, processed_item)

    LOGGER.debug(f"Exiting {config.name}")


class ChildProcessWorker(ABC):
    """Perform work in a child process.

    Input is expected on the thread input queue.
    This input is then forwarded to a multiprocessing queue.
    Work is then performed in the child process and returned through output queue.
    """

    def __init__(
        self,
        vis: Viseron,
        name: str,
        work: ChildProcessWork | None = None,
        *,
        stop_on_shutdown: bool = True,
        mp_context: BaseContext | None = None,
    ) -> None:
        if work is not None and mp_context:
            raise ValueError("mp_context is only supported for workers without work")
        implements_work_input = (
            type(self).work_input is not ChildProcessWorker.work_input
        )
        if work is None and not implements_work_input:
            raise TypeError(
                f"{type(self).__name__} needs work or to implement work_input"
            )
        if work is not None and (
            implements_work_input
            or type(self).process_initialization
            is not ChildProcessWorker.process_initialization
        ):
            raise TypeError(
                f"{type(self).__name__} is given work, so work_input and "
                "process_initialization of the worker would never be called"
            )
        self._name = name
        self._work = work
        self._mp_context: BaseContext
        if work is not None:
            self._mp_context = get_child_process_context()
        else:
            self._mp_context = mp_context or mp.get_context()

        self._process_frames_proc_exit = self._mp_context.Event()
        self._process_queue_lock = threading.Lock()
        self._output_queue_lock = threading.Lock()

        self.input_queue: Queue[Any] = Queue(maxsize=100)
        self._input_thread = RestartableThread(
            target=self._process_input_queue,
            name=f"child_process.{self._name}.input_thread",
            register=True,
            daemon=True,
        )
        self._input_thread.start()

        self._output_queue: mp.Queue = self._mp_context.Queue(maxsize=100)
        self._output_thread = RestartableThread(
            target=self._process_output_queue,
            name=f"child_process.{self._name}.output_thread",
            register=True,
            daemon=True,
        )
        self._output_thread.start()

        self._process_queue: mp.Queue = self._mp_context.Queue(maxsize=100)
        if work is not None:
            self._process_frames_proc = RestartableProcess(
                name=self.child_process_name,
                target=run_child_process_worker,
                create_args_method=self._create_process_args,
                daemon=True,
                context=CHILD_PROCESS_START_METHOD,
                child_logger_names=(LOGGER.name, *work.logger_names),
            )
        else:
            self._process_frames_proc = RestartableProcess(
                name=self.child_process_name,
                create_process_method=self._create_legacy_process,
            )
        self._process_frames_proc.start()

        self._event_listeners = []
        if stop_on_shutdown:
            self._event_listeners.append(
                vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self.stop)
            )

    def _recreate_queues(self) -> None:
        """Recreate the process queues before starting a new child process.

        Queue is recreated for each new process to avoid freezes when the process is
        killed.
        Also closes the old queues to avoid freezing Viseron restarts.
        """
        # The queues created in __init__ have not been used by a process yet
        if self._process_frames_proc.process is None:
            return
        LOGGER.debug(f"Setting process queues for {self.child_process_name}")
        with self._process_queue_lock, self._output_queue_lock:
            self._process_queue.close()
            self._output_queue.close()
            self._process_queue = self._mp_context.Queue(maxsize=100)
            self._output_queue = self._mp_context.Queue(maxsize=100)

    def _create_process_args(self) -> tuple[Any, ...]:
        """Return the args of a new child process.

        This method is called by RestartableProcess on every start.
        """
        assert self._work is not None  # For type checking  # noqa: S101
        self._recreate_queues()
        return (
            ChildProcessWorkerConfig(
                name=self.child_process_name,
                sensitive_strings=tuple(SensitiveInformationFilter.sensitive_strings),
                log_level=logging.getLogger().level,
            ),
            self._work,
            self._process_frames_proc_exit,
            self._process_queue,
            self._output_queue,
        )

    def _create_legacy_process(self) -> mp.Process:
        """Return the child process of a worker without work.

        This method is called by RestartableProcess on every start.
        """
        self._recreate_queues()
        return self._mp_context.Process(  # type: ignore[attr-defined]
            target=self._process_frames,
            name=self.child_process_name,
            args=(
                self._process_frames_proc_exit,
                self._process_queue,
                self._output_queue,
            ),
            daemon=True,
        )

    @property
    def child_process_name(self) -> str:
        """Return spawned child process name."""
        return f"viseron.child_process.{self._name}.process"

    def _process_input_queue(self) -> None:
        """Read from thread queue and put to multiprocessing queue."""
        while not self._process_frames_proc_exit.is_set():
            try:
                input_item = self.input_queue.get(timeout=1)
            except Empty:
                continue
            with self._process_queue_lock:
                pop_if_full(self._process_queue, input_item)

    def work_input(self, item):
        """Perform work on input item in child process, for workers without work."""
        raise NotImplementedError

    @abstractmethod
    def work_output(self, item):
        """Perform work on output item from child process."""

    def process_initialization(self) -> None:
        """Run initializations inside spawned process, for workers without work."""

    def _process_frames(
        self, exit_event: Event, process_queue: mp.Queue, output_queue: mp.Queue
    ) -> None:
        """Entrypoint of the child process of a worker without work."""
        os.setsid()
        remove_shm_from_resource_tracker()
        setproctitle.setproctitle(self.child_process_name)
        self.process_initialization()

        while not exit_event.is_set():
            try:
                item = process_queue.get(timeout=1)
            except Empty:
                continue
            processed_item = self.work_input(item)
            pop_if_full(output_queue, processed_item)

        LOGGER.debug(f"Exiting {self.child_process_name}")

    def _process_output_queue(self) -> None:
        """Read from multiprocessing queue and put to thread queue."""
        while not self._process_frames_proc_exit.is_set():
            try:
                with self._output_queue_lock:
                    item = self._output_queue.get(timeout=1)
            except Empty:
                continue
            self.work_output(item)

    def stop(self) -> None:
        """Stop detection process."""
        LOGGER.debug(f"Sending exit event to {self.child_process_name}")
        self._process_frames_proc_exit.set()

        self._input_thread.stop()
        self._output_thread.stop()
        self._input_thread.join(5)
        self._output_thread.join(5)

        self._process_frames_proc.join(5)
        self._process_frames_proc.terminate()
        self._process_frames_proc.kill()

        for unsubscribe in self._event_listeners:
            unsubscribe()

        self._process_queue.close()
        self._output_queue.close()

        LOGGER.debug(f"{self.child_process_name} exited")
