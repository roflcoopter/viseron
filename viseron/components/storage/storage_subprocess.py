"""Check storage tiers in a subprocess."""
from __future__ import annotations

import argparse
import datetime
import logging
import multiprocessing as mp
import subprocess as sp
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np
import psutil

from manager import connect
from viseron.components.storage.check_tier import Worker
from viseron.helpers.subprocess_worker import SubProcessWorker
from viseron.watchdog.subprocess_watchdog import RestartablePopen

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


class TierCheckWorker(SubProcessWorker):
    """Check tiers in a separate subprocess."""

    def __init__(self, vis: Viseron, cpulimit: int | None) -> None:
        self._cpulimit = cpulimit
        self._callbacks: dict[str, Callable[[DataItem], None]] = {}
        super().__init__(vis, f"{__name__}.tier_check_worker")

    def spawn_subprocess(self) -> RestartablePopen:
        """Spawn subprocess."""
        return RestartablePopen(
            (
                "python3 -u viseron/components/storage/storage_subprocess.py "
                f"--manager-port {self._server_port} "
                f"--manager-authkey {self._authkey_store.authkey} "
                f"--cpulimit {self._cpulimit} "
                f"--loglevel DEBUG"
            ).split(" "),
            name=self.subprocess_name,
            stdout=self._log_pipe,
            stderr=self._log_pipe,
        )

    def send_command(self, item: DataItem, callback: Callable[[DataItem], None]):
        """Send command to the subprocess."""
        # Generate a unique callback ID
        item.callback_id = str(id(callback))
        self._callbacks[item.callback_id] = callback
        # Send the command to the subprocess
        self.input_queue.put(item)

    def work_output(self, item: DataItem):
        """Perform work on output item from child process."""
        if not item.callback_id:
            LOGGER.error("No callback ID found in item")
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

    LOGGER.debug("Starting loop")
    while True:
        job = process_queue.get()
        worker.work_input(job)
        output_queue.put(job)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        LOGGER.debug("Storage tier check subprocess interrupted by user")
        sys.exit(0)
