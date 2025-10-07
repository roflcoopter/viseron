"""Helper to perform work in a child process."""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
from abc import ABC, abstractmethod
from multiprocessing.synchronize import Event
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

import setproctitle

from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.helpers import pop_if_full
from viseron.helpers.mprt_monkeypatch import remove_shm_from_resource_tracker
from viseron.watchdog.process_watchdog import RestartableProcess
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from viseron import Viseron


LOGGER = logging.getLogger(__name__)


class ChildProcessWorker(ABC):
    """Perform work in a child process.

    Input is expected on the thread input queue.
    This input is then forwarded to a multiprocessing queue.
    Work is then performed in the child process and returned through output queue.
    """

    def __init__(self, vis: Viseron, name: str) -> None:
        self._name = name

        self._process_frames_proc_exit = mp.Event()

        self.input_queue: Queue[Any] = Queue(maxsize=100)
        input_thread = RestartableThread(
            target=self._process_input_queue,
            name=f"child_process.{self._name}.input_thread",
            register=True,
            daemon=True,
        )
        input_thread.start()

        self._output_queue: mp.Queue = mp.Queue(maxsize=100)
        output_thread = RestartableThread(
            target=self._process_output_queue,
            name=f"child_process.{self._name}.output_thread",
            register=True,
            daemon=True,
        )
        output_thread.start()

        self._process_queue: mp.Queue = mp.Queue(maxsize=100)
        self._process_frames_proc = RestartableProcess(
            name=self.child_process_name,
            create_process_method=self.create_process,
        )
        self._process_frames_proc.start()

        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self.stop)

    def create_process(self) -> mp.Process:
        """Return process used by RestartableProcess.

        This method is called by RestartableProcess to create a new process.
        Queue is recreated for each new process to avoid freezes when the process is
        killed.
        Also closes the old queues to avoid freezing Viseron restarts.
        """
        LOGGER.debug(f"Setting process queues for {self.child_process_name}")
        if self._process_queue:
            self._process_queue.close()
        if self._output_queue:
            self._output_queue.close()
        self._process_queue = mp.Queue(maxsize=100)
        self._output_queue = mp.Queue(maxsize=100)
        return mp.Process(
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
            pop_if_full(self._process_queue, input_item)

    @abstractmethod
    def work_input(self, item):
        """Perform work on input item in child process."""

    @abstractmethod
    def work_output(self, item):
        """Perform work on output item from child process."""

    def process_initialization(self) -> None:
        """Run initializations inside spawned process."""

    def _process_frames(
        self, exit_event: Event, process_queue: mp.Queue, output_queue: mp.Queue
    ) -> None:
        """Process frame and send it to the detector."""
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
                item = self._output_queue.get(timeout=1)
            except Empty:
                continue
            self.work_output(item)

    def stop(self) -> None:
        """Stop detection process."""
        LOGGER.debug(f"Sending exit event to {self.child_process_name}")
        if self._process_queue:
            self._process_queue.close()
        if self._output_queue:
            self._output_queue.close()
        self._process_frames_proc_exit.set()
        self._process_frames_proc.join(5)
        self._process_frames_proc.terminate()
        self._process_frames_proc.kill()
        LOGGER.debug(f"{self.child_process_name} exited")
