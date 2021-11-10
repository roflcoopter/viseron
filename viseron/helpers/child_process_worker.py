"""Helper to perform work in a child process."""
import logging
import multiprocessing as mp
from abc import ABC, abstractmethod
from queue import Empty, Queue
from typing import Any

from setproctitle import setproctitle

from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.helpers import pop_if_full
from viseron.helpers.mprt_monkeypatch import (  # type: ignore
    remove_shm_from_resource_tracker,
)
from viseron.watchdog.thread_watchdog import RestartableThread

LOGGER = logging.getLogger(__name__)


class ChildProcessWorker(ABC):
    """Perform work in a child process.

    Input is expected on the thread input queue.
    This input is then forwarded to a multiprocessing queue.
    Work is then performed in the child process and returned through output queue.
    """

    def __init__(self, vis, name):
        self._name = name

        self.input_queue: Any = Queue(maxsize=100)
        input_thread = RestartableThread(
            target=self._process_input_queue,
            name=f"child_process.{self._name}.input_thread",
            register=True,
            daemon=True,
        )
        input_thread.start()

        self._output_queue: Any = mp.Queue(maxsize=100)
        output_thread = RestartableThread(
            target=self._process_output_queue,
            name=f"child_process.{self._name}.output_thread",
            register=True,
            daemon=True,
        )
        output_thread.start()

        self._process_frames_proc_exit = mp.Event()
        self._process_queue: Any = mp.Queue(maxsize=100)
        self._process_frames_proc = mp.Process(
            target=self._process_frames,
            name=self.child_process_name,
            args=(
                self._process_frames_proc_exit,
                self._process_queue,
                self._output_queue,
            ),
        )
        self._process_frames_proc.start()

        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self.stop)

    @property
    def child_process_name(self):
        """Return spawned child process name."""
        return f"child_process.{self._name}.process"

    def _process_input_queue(self):
        """Read from thread queue and put to multiprocessing queue."""
        while True:
            input_item = self.input_queue.get()
            self._process_queue.put(input_item)

    @abstractmethod
    def work_input(self, item):
        """Perform work on input item in child process."""

    @abstractmethod
    def work_output(self, item):
        """Perform work on output item from child process."""

    def _process_frames(self, exit_event, process_queue, output_queue):
        """Process frame and send it to the detector."""
        remove_shm_from_resource_tracker()
        setproctitle(self.child_process_name)

        while not exit_event.is_set():
            try:
                item = process_queue.get(timeout=1)
            except Empty:
                continue
            processed_item = self.work_input(item)
            pop_if_full(output_queue, processed_item)

        LOGGER.debug(f"Exiting {self.child_process_name}")

    def _process_output_queue(self):
        """Read from multiprocessing queue and put to thread queue."""
        while True:
            item = self._output_queue.get()
            self.work_output(item)

    def stop(self):
        """Stop detection process."""
        LOGGER.debug(f"Sending exit event to {self.child_process_name}")
        self._process_frames_proc_exit.set()
        self._process_frames_proc.join()
        LOGGER.debug(f"{self.child_process_name} exited")
