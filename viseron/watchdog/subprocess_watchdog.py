"""Watchdog for long-running threads."""
from __future__ import annotations

import logging
import subprocess as sp
from typing import TYPE_CHECKING

from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.helpers import utcnow
from viseron.watchdog import WatchDog

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler

LOGGER = logging.getLogger(__name__)


class RestartablePopen:
    """A restartable subprocess.

    Like subprocess.Popen, but registers itself in a watchdog which monitors the
    process.
    """

    def __init__(
        self,
        *args,
        name=None,
        grace_period=20,
        register=True,
        stage: str | None = VISERON_SIGNAL_SHUTDOWN,
        start_new_session: bool = True,
        **kwargs,
    ) -> None:
        self._args = args
        self._name = name
        self._grace_period = grace_period
        self._kwargs = kwargs
        self._kwargs["start_new_session"] = start_new_session
        self._subprocess: sp.Popen | None = None
        self._started = False
        self.start()
        if register:
            SubprocessWatchDog.register(self)
        setattr(self, "__stage__", stage)

    def __getattr__(self, attr):
        """Forward all undefined attribute calls to sp.Popen."""
        if attr in self.__class__.__dict__:
            return getattr(self, attr)
        return getattr(self._subprocess, attr)

    def __repr__(self):
        """Return string representation of the subprocess."""
        return (
            f"<RestartablePopen name={self._name} "
            f"pid={self._subprocess.pid if self._subprocess else None}>"
        )

    @property
    def name(self):
        """Return subprocess name."""
        return self._name

    @property
    def grace_period(self):
        """Return subprocess grace period."""
        return self._grace_period

    @property
    def subprocess(self):
        """Return subprocess."""
        return self._subprocess

    @property
    def started(self):
        """Return if subprocess has started."""
        return self._started

    @property
    def start_time(self):
        """Return subprocess start time."""
        return self._start_time

    def start(self) -> None:
        """Start the subprocess."""
        self._subprocess = sp.Popen(
            *self._args,
            **self._kwargs,
        )
        self._start_time = utcnow().timestamp()
        self._started = True

    def restart(self) -> None:
        """Restart the subprocess."""
        self._started = False
        if self._subprocess:
            self._subprocess.terminate()
            try:
                self._subprocess.communicate(timeout=5)
            except sp.TimeoutExpired:
                LOGGER.debug("Subprocess did not terminate, killing instead.")
                self._subprocess.kill()
                self._subprocess.communicate()
        self.start()

    def terminate(self) -> None:
        """Terminate the subprocess."""
        self._started = False
        SubprocessWatchDog.unregister(self)
        if self._subprocess:
            self._subprocess.terminate()


class SubprocessWatchDog(WatchDog):
    """A watchdog for long running processes."""

    registered_items: list[RestartablePopen] = []
    started: bool = False

    def __init__(self, background_scheduler: BackgroundScheduler) -> None:
        super().__init__()
        background_scheduler.add_job(
            self.watchdog,
            "interval",
            id="subprocess_watchdog",
            name="subprocess_watchdog",
            seconds=15,
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        # Clear registered items on creation, useful when start watchdogs in child procs
        SubprocessWatchDog.registered_items = []
        SubprocessWatchDog.started = True

    def watchdog(self) -> None:
        """Check for stopped processes and restart them."""
        for registered_process in self.registered_items:
            if not registered_process.started:
                continue
            if registered_process.subprocess.poll() is None:
                continue
            now = utcnow().timestamp()
            if now - registered_process.start_time < registered_process.grace_period:
                continue

            LOGGER.error(f"Process {registered_process.name} has exited, restarting")
            registered_process.restart()
