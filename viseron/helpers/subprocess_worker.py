"""Helper to perform work in a separate python shell."""

from __future__ import annotations

import logging
import multiprocessing as mp
import secrets
import subprocess as sp
from abc import ABC, abstractmethod
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

from manager import QueueManager, start, stop
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.helpers import get_free_port, pop_if_full
from viseron.helpers.logs import LogPipe
from viseron.helpers.storage import Storage
from viseron.watchdog.subprocess_watchdog import RestartablePopen
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from viseron import Viseron

BASE_MANAGER_AUTHKEY_STORAGE_KEY = "base_manager_authkey"

LOGGER = logging.getLogger(__name__)


class SubProcessWorker(ABC):
    """Perform work in a spawned subprocess.

    Input is expected on the thread input queue.
    This input is then forwarded to another queue which is shared with a spawned
    python shell using QueueManager.
    Work is then performed in the child process and returned through output queue.
    """

    def __init__(self, vis: Viseron, name) -> None:
        self._name = name

        self._authkey_store = BaseManagerAuthkeyStore(vis)
        self._server_port = get_free_port(port=50000)

        self._process_frames_proc_exit = mp.Event()

        self.input_queue: Any = Queue(maxsize=100)
        self._input_thread = RestartableThread(
            target=self._process_input_queue,
            name=f"subprocess.{self._name}.input_thread",
            register=True,
            daemon=True,
        )
        self._input_thread.start()

        self._output_queue: Any = Queue(maxsize=100)
        self._output_thread = RestartableThread(
            target=self._process_output_queue,
            name=f"subprocess.{self._name}.output_thread",
            register=True,
            daemon=True,
        )
        self._output_thread.start()

        self._log_pipe = LogPipe(
            logging.getLogger(f"{self.__module__}.subprocess"),
            output_level_func=self.get_loglevel,
        )
        self._process_queue: Any = Queue(maxsize=100)
        self._server = Server(
            "127.0.0.1",
            self._server_port,
            self._authkey_store.authkey,
            self._process_queue,
            self._output_queue,
        )

        LOGGER.debug("Spawned subprocess")
        self._process_frames_proc = self.spawn_subprocess()
        LOGGER.debug(f"Started subprocess {self.subprocess_name}")

        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self.stop)

    @property
    def subprocess_name(self) -> str:
        """Return spawned subprocess name."""
        return f"subprocess.{self._name}.process"

    def get_loglevel(self, log_str: str) -> tuple[int, str]:
        """Return loglevel for log string from subprocess."""
        loglevel_str = log_str.split(" ")[0]
        return logging.getLevelName(loglevel_str), log_str.split(" ", 1)[-1]

    def _process_input_queue(self) -> None:
        """Read from thread queue and put to multiprocessing queue."""
        while not self._process_frames_proc_exit.is_set():
            try:
                input_item = self.input_queue.get(timeout=1)
            except Empty:
                continue
            pop_if_full(self._process_queue, input_item)

    @abstractmethod
    def spawn_subprocess(self) -> RestartablePopen:
        """Spawn subprocess."""

    @abstractmethod
    def work_output(self, item):
        """Perform work on output item from child process."""

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
        LOGGER.debug(f"Sending exit event to {self.subprocess_name}")
        self._server.stop_server()
        self._input_thread.stop()
        self._output_thread.stop()
        self._process_frames_proc_exit.set()
        self._process_frames_proc.terminate()
        try:
            self._process_frames_proc.communicate(timeout=5)
        except sp.TimeoutExpired:
            LOGGER.debug(
                f"Subprocess {self.subprocess_name} did not terminate, "
                "killing instead."
            )
            self._process_frames_proc.kill()
            self._process_frames_proc.communicate()
        self._log_pipe.close()
        LOGGER.debug(f"{self.subprocess_name} exited")


class Server:
    """BaseManager server."""

    def __init__(
        self,
        address: str,
        port: int,
        authkey: str,
        process_queue: Queue,
        output_queue: Queue,
    ):
        self.address = address
        self.port = port
        self.authkey = authkey
        self.process_queue = process_queue
        self.output_queue = output_queue

        self._manager: QueueManager | None = None
        self._server_thread = RestartableThread(
            target=self.start_server,
            name="queue_manager.server",
            register=True,
            daemon=True,
        )
        self._server_thread.start()

    def start_server(self):
        """Start the server."""
        LOGGER.debug("Starting queue manager server")
        self._manager = start(
            address=self.address,
            port=self.port,
            authkey=self.authkey,
            process_queue=self.process_queue,
            output_queue=self.output_queue,
        )
        try:
            self._manager.get_server().serve_forever()
        except SystemExit:
            LOGGER.debug("Stopped serving queue manager server")

    def stop_server(self):
        """Stop the server."""
        self._server_thread.stop()
        LOGGER.debug("Stopping queue manager server")
        if self._manager:
            stop(
                address=self.address,
                port=self.port,
                authkey=self.authkey,
            )
        LOGGER.debug("Queue manager server stopped")


class BaseManagerAuthkeyStore:
    """BaseManager authkey store."""

    def __init__(self, vis: Viseron) -> None:
        self._store = Storage(vis, BASE_MANAGER_AUTHKEY_STORAGE_KEY)
        self._data = self._store.load()

    @property
    def authkey(self):
        """Return authkey."""
        if "authkey" not in self._data:
            self._data["authkey"] = secrets.token_hex(16)
            self._store.save(self._data)
        return self._data["authkey"]
