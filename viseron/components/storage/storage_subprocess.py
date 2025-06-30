"""Check storage tiers in a subprocess."""
from __future__ import annotations

import argparse
import datetime
import logging
import multiprocessing as mp
import subprocess as sp
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from queue import Empty, Queue
from typing import TYPE_CHECKING, Literal

import numpy as np
import psutil
from apscheduler.schedulers.background import BackgroundScheduler

from manager import connect
from viseron.components.storage.check_tier import Worker
from viseron.helpers.subprocess_worker import SubProcessWorker
from viseron.watchdog.subprocess_watchdog import RestartablePopen
from viseron.watchdog.thread_watchdog import RestartableThread, ThreadWatchDog

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)


@dataclass
class DataItem:
    """Data item to be processed by the worker."""

    cmd: Literal["check_tier"]
    camera_identifier: str
    tier_id: int
    category: str
    subcategories: list[str]
    throttle_period: datetime.timedelta
    max_bytes: int
    min_age: datetime.timedelta
    max_age: datetime.timedelta
    min_bytes: int
    files_enabled: bool = True
    events_enabled: bool = False
    events_max_bytes: int | None = None
    events_min_age: datetime.timedelta | None = None
    events_max_age: datetime.timedelta | None = None
    events_min_bytes: int | None = None
    callback_id: str | None = None
    data: np.ndarray | None = None
    error: str | None = None

    @property
    def throttle_key(self) -> str:
        """Generate a unique key for throttling."""
        return (
            f"{self.camera_identifier}_"
            f"{self.tier_id}_{self.category}_"
            f"{self.subcategories[0]}"
        )


@dataclass
class DataItemMoveFile:
    """Data item to be processed by the worker for moving files."""

    cmd: Literal["move_file"]
    src: str
    dst: str
    callback_id: str | None = None
    error: str | None = None


@dataclass
class DataItemDeleteFile:
    """Data item to be processed by the worker for deleting files."""

    cmd: Literal["delete_file"]
    src: str
    callback_id: str | None = None
    error: str | None = None


class TierCheckWorker(SubProcessWorker):
    """Check tiers in a separate subprocess."""

    def __init__(self, vis: Viseron, cpulimit: int | None, workers: int) -> None:
        self._cpulimit = cpulimit
        self._workers = workers
        self._callbacks: dict[
            str, Callable[[DataItem | DataItemMoveFile | DataItemDeleteFile], None]
        ] = {}
        super().__init__(vis, f"{__name__}.tier_check_worker", qsize=0)

    def spawn_subprocess(self) -> RestartablePopen:
        """Spawn subprocess."""
        return RestartablePopen(
            (
                "python3 -u viseron/components/storage/storage_subprocess.py "
                f"--manager-port {self._server_port} "
                f"--manager-authkey {self._authkey_store.authkey} "
                f"--cpulimit {self._cpulimit} "
                f"--workers {self._workers} "
                f"--loglevel DEBUG"
            ).split(" "),
            name=self.subprocess_name,
            stdout=self._log_pipe,
            stderr=self._log_pipe,
        )

    def send_command(
        self,
        item: DataItem | DataItemMoveFile | DataItemDeleteFile,
        callback: Callable[[DataItem | DataItemMoveFile | DataItemDeleteFile], None]
        | None,
    ):
        """Send command to the subprocess."""
        if callback is not None:
            item.callback_id = str(id(callback))
            self._callbacks[item.callback_id] = callback
        self.input_queue.put(item)

    def work_output(self, item: DataItem | DataItemMoveFile | DataItemDeleteFile):
        """Perform work on output item from child process."""
        if not item.callback_id:
            return

        callback = self._callbacks.pop(item.callback_id, None)
        if callback:
            callback(item)
        else:
            LOGGER.warning("No callback found")


def setup_logger(loglevel: str) -> None:
    """Log to stdout without any formatting.

    Viserons main log formatter takes care of the format in the main process.
    """
    root = logging.getLogger()
    root.setLevel(loglevel)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(loglevel)
    formatter = logging.Formatter("%(levelname)s %(message)s")
    handler.setFormatter(formatter)
    root.addHandler(handler)


def get_parser() -> argparse.ArgumentParser:
    """Get parser for script."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--manager-port", help="Port for the Manager", required=True)
    parser.add_argument(
        "--manager-authkey", help="Password for the Manager", required=True
    )

    parser.add_argument(
        "--cpulimit",
        help="CPU limit for the subprocess",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--workers",
        help="Number of worker threads",
        type=int,
        default=4,
    )
    parser.add_argument(
        "--loglevel",
        help="Loglevel",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    return parser


def initializer(cpulimit: int | None):
    """Initialize engine in process."""
    # Limit CPU by spawning cpulimit
    pid = mp.current_process().pid
    if pid:
        ps = psutil.Process(pid)
        ps.nice(20)
    if pid and cpulimit is not None:
        command = f"cpulimit -l {cpulimit} -p {pid} -z -q"
        LOGGER.debug(f"Running command: {command}")
        sp.Popen(command, shell=True)


def worker_task(worker: Worker, process_queue: Queue, output_queue: Queue):
    """Worker thread task."""
    while True:
        try:
            job = process_queue.get(block=True, timeout=1)
            worker.work_input(job)
            output_queue.put(job)
        except Empty:
            continue
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception(f"Error in worker thread: {exc}")


def main():
    """Run tier check in a subprocess."""
    parser = get_parser()
    args = parser.parse_args()
    setup_logger(args.loglevel)
    process_queue, output_queue = connect(
        "127.0.0.1", int(args.manager_port), args.manager_authkey
    )

    initializer(
        cpulimit=args.cpulimit,
    )

    worker = Worker()
    # Run scheduler and watchdog in the subprocess since the Viseron main process
    # watchdog is not available in the subprocess.
    logging.getLogger("apscheduler.scheduler").setLevel(logging.ERROR)
    logging.getLogger("apscheduler.executors").setLevel(logging.ERROR)
    background_scheduler = BackgroundScheduler(timezone="UTC", daemon=True)
    background_scheduler.start()
    ThreadWatchDog(background_scheduler)

    LOGGER.debug(f"Starting {args.workers} worker threads")
    threads: list[RestartableThread] = []
    for i in range(args.workers):
        thread = RestartableThread(
            name=f"storage_subprocess.worker.{i}",
            target=worker_task,
            args=(worker, process_queue, output_queue),
            daemon=True,
        )
        thread.start()
        threads.append(thread)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        LOGGER.debug("Storage tier check subprocess interrupted by user")
        sys.exit(0)
