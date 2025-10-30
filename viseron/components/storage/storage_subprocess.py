"""Check storage tiers in a subprocess."""
from __future__ import annotations

import argparse
import datetime
import logging
import multiprocessing as mp
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
    drain: bool
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
        RestartablePopen(
            command,
            register=False,
            shell=True,
        )


def worker_task_files(
    worker: Worker,
    file_queue: Queue[DataItemDeleteFile | DataItemMoveFile],
    output_queue: Queue[DataItemDeleteFile | DataItemMoveFile],
):
    """Worker thread that only processes file operation commands."""
    while True:
        try:
            job = file_queue.get(timeout=1)
            worker.work_input(job)
            output_queue.put(job)
        except Empty:
            continue
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception(f"Error in file worker thread: {exc}")


def worker_task_mixed(
    worker: Worker,
    check_queue: Queue[DataItem],
    file_queue: Queue[DataItemDeleteFile | DataItemMoveFile],
    output_queue: Queue[DataItem | DataItemDeleteFile | DataItemMoveFile],
    name: str,
):
    """Worker thread that prioritizes file operations but also handles check_tier.

    This ensures that file operations are not blocked by slow check_tier jobs.
    """
    job: DataItem | DataItemDeleteFile | DataItemMoveFile
    while True:
        try:
            try:
                job = file_queue.get_nowait()
            except Empty:
                job = check_queue.get(timeout=1)
            worker.work_input(job)
            output_queue.put(job)
        except Empty:
            continue
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception(f"Error in mixed worker thread {name}: {exc}")


def dispatcher_task(
    process_queue: Queue[DataItem | DataItemDeleteFile | DataItemMoveFile],
    check_queue: Queue[DataItem],
    file_queue: Queue[DataItemDeleteFile | DataItemMoveFile],
):
    """Dispatcher thread routing jobs to dedicated queues.

    check_tier commands can be slow. File operations should not be blocked by them,
    so they get their own queue and worker.
    """
    while True:
        try:
            job = process_queue.get(timeout=1)
        except Empty:
            continue

        try:
            if job.cmd == "check_tier":
                check_queue.put(job)
            elif job.cmd in ("move_file", "delete_file"):
                file_queue.put(job)
            else:
                LOGGER.debug("Unknown command %s", job.cmd)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception(f"Dispatcher error routing job: {exc}")


def main():
    """Run tier check in a subprocess."""
    parser = get_parser()
    args = parser.parse_args()
    setup_logger(args.loglevel)
    process_queue: Queue[DataItem | DataItemDeleteFile | DataItemMoveFile]
    output_queue: Queue[DataItem | DataItemDeleteFile | DataItemMoveFile]
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

    check_queue: Queue[DataItem] = Queue()
    file_queue: Queue[DataItemDeleteFile | DataItemMoveFile] = Queue()

    dispatcher = RestartableThread(
        name="storage_subprocess.dispatcher",
        target=dispatcher_task,
        args=(process_queue, check_queue, file_queue),
        daemon=True,
    )
    dispatcher.start()

    for i in range(args.workers):
        thread = RestartableThread(
            name=f"storage_subprocess.mixed_worker.{i}",
            target=worker_task_mixed,
            args=(
                worker,
                check_queue,
                file_queue,
                output_queue,
                f"mixed_worker.{i}",
            ),
            daemon=True,
        )
        thread.start()

    thread = RestartableThread(
        name="storage_subprocess.file_worker",
        target=worker_task_files,
        args=(worker, file_queue, output_queue),
        daemon=True,
    )
    thread.start()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        LOGGER.debug("Storage tier check subprocess interrupted by user")
        sys.exit(0)
