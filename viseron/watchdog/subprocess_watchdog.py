"""Watchdog for long-running threads."""
import datetime
import logging
import subprocess as sp
from typing import List

from viseron.watchdog import WatchDog

LOGGER = logging.getLogger(__name__)


class RestartablePopen:
    """A restartable subprocess.

    Like subprocess.Popen, but registers itself in a watchdog which monitors the
    process.
    """

    def __init__(
        self, *args, name=None, grace_period=20, register=True, **kwargs
    ) -> None:
        self._args = args
        self._name = name
        self._grace_period = grace_period
        self._kwargs = kwargs
        self._subprocess = None
        self._started = False
        self.start()
        if register:
            SubprocessWatchDog.register(self)

    def __getattr__(self, attr):
        """Forward all undefined attribute calls to sp.Popen."""
        if attr in self.__class__.__dict__:
            return getattr(self, attr)
        return getattr(self._subprocess, attr)

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
        self._start_time = datetime.datetime.now().timestamp()
        self._started = True

    def restart(self) -> None:
        """Restart the subprocess."""
        self._started = False
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
        self._subprocess.terminate()


class SubprocessWatchDog(WatchDog):
    """A watchdog for long running processes."""

    registered_items: List[RestartablePopen] = []

    def __init__(self) -> None:
        super().__init__()
        self._scheduler.add_job(self.watchdog, "interval", seconds=15)

    def watchdog(self) -> None:
        """Check for stopped processes and restart them."""
        for registered_process in self.registered_items:
            if not registered_process.started:
                continue
            if registered_process.subprocess.poll() is None:
                continue
            now = datetime.datetime.now().timestamp()
            if now - registered_process.start_time < registered_process.grace_period:
                continue

            LOGGER.error(f"Process {registered_process.name} has exited, restarting")
            registered_process.restart()
