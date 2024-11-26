"""Watchdog for long-running processes."""
from __future__ import annotations

import logging
import multiprocessing as mp
from collections.abc import Callable
from typing import TYPE_CHECKING

from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.helpers import utcnow
from viseron.watchdog import WatchDog

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)


class RestartableProcess:
    """A restartable process.

    Like multiprocessing.Process, but registers itself in a watchdog which monitors the
    process.
    """

    def __init__(
        self,
        *args,
        name=None,
        grace_period=20,
        register=True,
        stage: str | None = VISERON_SIGNAL_SHUTDOWN,
        create_process_method: Callable[[], mp.Process] | None = None,
        **kwargs,
    ) -> None:
        self._args = args
        self._name = name
        self._grace_period = grace_period
        self._kwargs = kwargs
        self._kwargs["name"] = name
        self._process: mp.Process | None = None
        self._started = False
        self._start_time: float | None = None
        self._register = register
        self._create_process_method = create_process_method
        if self._register:
            ProcessWatchDog.register(self)
        setattr(self, "__stage__", stage)

    def __getattr__(self, attr):
        """Forward all undefined attribute calls to mp.Process."""
        if attr in self.__class__.__dict__:
            return getattr(self, attr)
        return getattr(self._process, attr)

    @property
    def name(self):
        """Return process name."""
        return self._name

    @property
    def grace_period(self) -> int:
        """Return process grace period."""
        return self._grace_period

    @property
    def process(self) -> mp.Process | None:
        """Return process."""
        return self._process

    @property
    def started(self) -> bool:
        """Return if process has started."""
        return self._started

    @property
    def start_time(self) -> float | None:
        """Return process start time."""
        return self._start_time

    @property
    def exitcode(self) -> int | None:
        """Return process exit code."""
        if self._process:
            return self._process.exitcode
        return 0

    def start(self) -> None:
        """Start the process."""
        if self._create_process_method:
            self._process = self._create_process_method()
        else:
            self._process = mp.Process(
                *self._args,
                **self._kwargs,
            )
        self._start_time = utcnow().timestamp()
        self._started = True
        self._process.start()

    def restart(self, timeout: float | None = None) -> None:
        """Restart the process."""
        self._started = False
        if self._process:
            self._process.terminate()
            self._process.join(timeout=timeout)
            self._process.kill()
        self.start()

    def is_alive(self) -> bool:
        """Return if the process is alive."""
        if self._process:
            return self._process.is_alive()
        return False

    def join(self, timeout: float | None = None) -> None:
        """Join the process."""
        if self._process:
            self._process.join(timeout=timeout)

    def terminate(self) -> None:
        """Terminate the process."""
        self._started = False
        ProcessWatchDog.unregister(self)
        if self._process:
            self._process.terminate()

    def kill(self) -> None:
        """Kill the process."""
        self._started = False
        ProcessWatchDog.unregister(self)
        if self._process:
            self._process.kill()


class ProcessWatchDog(WatchDog):
    """A watchdog for long running processes."""

    registered_items: list[RestartableProcess] = []

    def __init__(self, vis: Viseron) -> None:
        super().__init__()
        vis.background_scheduler.add_job(
            self.watchdog, "interval", name="process_watchdog", seconds=15
        )

    def watchdog(self) -> None:
        """Check for stopped processes and restart them."""
        for registered_process in self.registered_items:
            if not registered_process.started:
                continue
            if registered_process.is_alive():
                continue

            now = utcnow().timestamp()
            if (
                registered_process.start_time
                and now - registered_process.start_time
                < registered_process.grace_period
            ):
                continue

            LOGGER.error(f"Process {registered_process.name} has exited, restarting")
            registered_process.restart()
