"""Watchdog for long-running processes."""
from __future__ import annotations

import logging
import multiprocessing as mp
import os
from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import SchedulerNotRunningError

from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.helpers import utcnow
from viseron.watchdog import WatchDog
from viseron.watchdog.subprocess_watchdog import SubprocessWatchDog
from viseron.watchdog.thread_watchdog import ThreadWatchDog

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
        start_watchdogs: bool = False,
        **kwargs,
    ) -> None:
        self._args = args
        self._name = name
        self._grace_period = grace_period
        self._kwargs = kwargs
        self._kwargs["name"] = name
        self._original_target: Callable | None = self._kwargs.get("target")
        self._process: mp.Process | None = None
        self._started = False
        self._start_time: float | None = None
        self._register = register
        self._create_process_method = create_process_method
        self._start_watchdogs = start_watchdogs
        self._background_scheduler: BackgroundScheduler | None = None
        self._thread_watchdog: ThreadWatchDog | None = None
        self._subprocess_watchdog: SubprocessWatchDog | None = None
        self._process_watchdog: ProcessWatchDog | None = None
        if self._register:
            ProcessWatchDog.register(self)
        setattr(self, "__stage__", stage)

    def __getattr__(self, attr):
        """Forward all undefined attribute calls to mp.Process."""
        if attr in self.__class__.__dict__:
            return getattr(self, attr)
        return getattr(self._process, attr)

    def __repr__(self):
        """Return string representation of the process."""
        return (
            f"<RestartableProcess name={self._name} "
            f"pid={self._process.pid if self._process else None}>"
        )

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
        # Always (re)set the wrapped target so that restarts also create a new
        # process that calls os.setsid() before executing the user target.
        if self._original_target:
            original_target = self._original_target

            def wrapped_target(*targs, **tkwargs):
                """Wrap original target to establish its own session ID.

                Creating a new session (setsid) ensures the child process becomes
                the leader of a new session and process group. This makes signal
                management (e.g. terminating entire groups) more robust and
                prevents the process from receiving signals intended for the
                parent group.

                Watchdogs are also started inside the process if enabled.
                """
                os.setsid()
                ThreadWatchDog.started = False
                SubprocessWatchDog.started = False
                ProcessWatchDog.started = False
                if self._start_watchdogs:
                    self._start_local_watchdogs()
                original_target(*targs, **tkwargs)

            self._kwargs["target"] = wrapped_target

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

    def stop(self) -> None:
        """Stop (unregister) the process."""
        self._started = False
        ProcessWatchDog.unregister(self)

        if (
            self._thread_watchdog
            and self._subprocess_watchdog
            and self._process_watchdog
        ):
            self._thread_watchdog.stop()
            self._subprocess_watchdog.stop()
            self._process_watchdog.stop()

        if self._background_scheduler:
            try:
                self._background_scheduler.remove_all_jobs()
                self._background_scheduler.shutdown(wait=False)
            except SchedulerNotRunningError as err:
                LOGGER.warning(f"Failed to shutdown scheduler: {err}")

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

    def _start_local_watchdogs(self) -> None:
        """Start local watchdogs inside the process.

        Threads, subprocesses and processes are monitored in the parent,
        but if the process itself spawns long-running entities, those need to
        be monitored as well.
        """
        self._background_scheduler = BackgroundScheduler(timezone="UTC", daemon=True)
        self._background_scheduler.start()
        self._thread_watchdog = ThreadWatchDog(self._background_scheduler)
        self._subprocess_watchdog = SubprocessWatchDog(self._background_scheduler)
        self._process_watchdog = ProcessWatchDog(self._background_scheduler)


class ProcessWatchDog(WatchDog):
    """A watchdog for long running processes."""

    registered_items: list[RestartableProcess] = []
    started: bool = False

    def __init__(self, background_scheduler: BackgroundScheduler) -> None:
        super().__init__()
        background_scheduler.add_job(
            self.watchdog,
            "interval",
            id="process_watchdog",
            name="process_watchdog",
            seconds=15,
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        # Clear registered items on creation, useful when start watchdogs in child procs
        ProcessWatchDog.registered_items = []
        ProcessWatchDog.started = True

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
