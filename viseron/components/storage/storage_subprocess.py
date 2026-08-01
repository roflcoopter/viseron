"""Check storage tiers in a subprocess."""

from __future__ import annotations

import argparse
import itertools
import logging
import multiprocessing as mp
import sys
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from queue import Empty, Queue
from typing import TYPE_CHECKING, Literal

import psutil
import setproctitle
from apscheduler.schedulers.background import BackgroundScheduler

from manager import connect
from viseron.components.storage.check_tier import Worker
from viseron.helpers.subprocess_worker import SubProcessWorker
from viseron.watchdog.subprocess_watchdog import RestartablePopen
from viseron.watchdog.thread_watchdog import RestartableThread, ThreadWatchDog

if TYPE_CHECKING:
    import datetime
    from collections.abc import Callable

    import numpy as np

    from viseron import Viseron

LOGGER = logging.getLogger(__name__)

# Upper bound on the parent's pending-callback dict. check_tier jobs are sent
# with a callback, but DedupCheckQueue drops superseded jobs in the subprocess
# so those jobs never produce a reply and their callbacks would otherwise stay
# in _callbacks forever. Evicting the oldest entries FIFO past this cap keeps
# the dict bounded; a lost entry only means a future reply becomes a no-op pop.
MAX_PENDING_CALLBACKS = 10_000


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


class DedupCheckQueue:
    """FIFO queue for check_tier jobs that dedupes by ``throttle_key``.

    Drop-in replacement for ``queue.Queue`` on the check_tier dispatch path:
    same ``.put(item)`` / ``.get(timeout=...)`` signature (``queue.Empty`` is
    raised on timeout), so ``dispatcher_task`` and ``worker_task_mixed`` need no
    other change.

    A check_tier job reads the *current* database and filesystem state, so when
    several jobs for the same ``throttle_key`` are queued only the most recent
    one carries useful information. When the workers are saturated by
    ``file_queue`` (move_file/delete_file take ~100 ms while a tier check can
    take tens of seconds), a plain unbounded ``Queue`` lets pending ``DataItem``
    instances accumulate without limit and the subprocess RSS grows unbounded.
    Deduping on insert bounds the queue to ``N_cameras * N_throttle_keys``
    regardless of how fast jobs are enqueued.

    ``file_queue`` is intentionally left as a plain ``Queue``: move_file and
    delete_file are per-file destructive operations and must not be dropped.
    """

    def __init__(self) -> None:
        self._items: OrderedDict[str, DataItem] = OrderedDict()
        self._cond = threading.Condition()

    def put(self, item: DataItem) -> None:
        """Insert a job, replacing any queued job with the same throttle_key."""
        with self._cond:
            # Drop the stale entry first so the replacement is appended at the
            # tail and processed in arrival order relative to other keys.
            self._items.pop(item.throttle_key, None)
            self._items[item.throttle_key] = item
            self._cond.notify()

    def get(self, timeout: float | None = None) -> DataItem:
        """Pop the oldest job, blocking up to ``timeout`` seconds.

        Raises ``queue.Empty`` if no job becomes available within ``timeout``.
        """
        with self._cond:
            end_time = None if timeout is None else time.monotonic() + timeout
            while not self._items:
                if end_time is None:
                    self._cond.wait()
                else:
                    remaining = end_time - time.monotonic()
                    if remaining <= 0:
                        raise Empty
                    self._cond.wait(remaining)
            _, item = self._items.popitem(last=False)
            return item

    def qsize(self) -> int:
        """Return the number of queued jobs."""
        with self._cond:
            return len(self._items)


class TierCheckWorker(SubProcessWorker):
    """Check tiers in a separate subprocess."""

    def __init__(self, vis: Viseron, cpulimit: int | None, workers: int) -> None:
        self._cpulimit = cpulimit
        self._workers = workers
        # OrderedDict so the oldest pending callback can be evicted FIFO once
        # MAX_PENDING_CALLBACKS is reached. send_command (caller thread) and
        # work_output (subprocess output thread) both mutate _callbacks, so all
        # access is guarded by _callbacks_lock to keep the insert+len+popitem
        # sequence atomic against concurrent pops.
        self._callbacks: OrderedDict[
            str, Callable[[DataItem | DataItemMoveFile | DataItemDeleteFile], None]
        ] = OrderedDict()
        self._callbacks_lock = threading.Lock()
        # Monotonic callback ids. str(id(callback)) is unsafe here: bound
        # methods like self.on_check_tier_result are created lazily on each
        # attribute access, so CPython may reuse a freed method's address and
        # two handlers could collide on the same id, routing a reply to the
        # wrong callback. itertools.count.__next__ is atomic under the GIL.
        self._next_callback_id = itertools.count(1)
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
    ) -> None:
        """Send command to the subprocess."""
        evicted: str | None = None
        if callback is not None:
            item.callback_id = str(next(self._next_callback_id))
            with self._callbacks_lock:
                self._callbacks[item.callback_id] = callback
                if len(self._callbacks) > MAX_PENDING_CALLBACKS:
                    evicted, _ = self._callbacks.popitem(last=False)
        if evicted is not None:
            # Means the subprocess is taking longer to reply than we can
            # generate new jobs. The evicted callback's reply will later
            # surface as a benign "No callback found" miss in work_output.
            LOGGER.warning(
                "Pending callbacks exceeded %d, evicted oldest id=%s; "
                "its reply will be dropped when it arrives",
                MAX_PENDING_CALLBACKS,
                evicted,
            )
        self.input_queue.put(item)

    def work_output(
        self, item: DataItem | DataItemMoveFile | DataItemDeleteFile
    ) -> None:
        """Perform work on output item from child process."""
        if not item.callback_id:
            return

        with self._callbacks_lock:
            callback = self._callbacks.pop(item.callback_id, None)
        if callback:
            callback(item)
        else:
            # Expected when the callback was FIFO-evicted in send_command
            # because MAX_PENDING_CALLBACKS was exceeded; logged at DEBUG so
            # it doesn't spam under sustained load.
            LOGGER.debug(
                "No callback found for id=%s cmd=%s",
                item.callback_id,
                item.cmd,
            )


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


def initializer(cpulimit: int | None) -> None:
    """Initialize engine in process."""
    # Limit CPU by spawning cpulimit
    pid = mp.current_process().pid
    if pid:
        ps = psutil.Process(pid)
        ps.nice(20)
    if pid and cpulimit is not None:
        command = ["cpulimit", "-l", str(cpulimit), "-p", str(pid), "-z", "-q"]
        LOGGER.debug(f"Running command: {command}")
        RestartablePopen(
            command,
            register=False,
        )
    # Set process name
    setproctitle.setproctitle(f"viseron_storage_subprocess_{pid}")


def worker_task_files(
    worker: Worker,
    file_queue: Queue[DataItemDeleteFile | DataItemMoveFile],
    output_queue: Queue[DataItemDeleteFile | DataItemMoveFile],
) -> None:
    """Worker thread that only processes file operation commands."""
    while True:
        try:
            job = file_queue.get(timeout=1)
            worker.work_input(job)
            output_queue.put(job)
        except Empty:
            continue
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Error in file worker thread")


def worker_task_mixed(
    worker: Worker,
    check_queue: DedupCheckQueue,
    file_queue: Queue[DataItemDeleteFile | DataItemMoveFile],
    output_queue: Queue[DataItem | DataItemDeleteFile | DataItemMoveFile],
    name: str,
) -> None:
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
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(f"Error in mixed worker thread {name}")


def dispatcher_task(
    process_queue: Queue[DataItem | DataItemDeleteFile | DataItemMoveFile],
    check_queue: DedupCheckQueue,
    file_queue: Queue[DataItemDeleteFile | DataItemMoveFile],
) -> None:
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
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Dispatcher error routing job")


def main() -> None:
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

    check_queue = DedupCheckQueue()
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
