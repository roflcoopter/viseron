"""Watchdog for long-running threads."""
import datetime
import logging
import threading
from typing import Callable, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler

LOGGER = logging.getLogger(__name__)


class RestartableThread(threading.Thread):
    """Thread which can be reinstantiated with the clone method.
    Arguments are the same as a standard Thread, with a few additions:
    :param stop_target: (default=None)
        A callable which is called when stop method is called.
    :param poll_timer: (default=None)
        A mutable list which contains a single element with a timestamp
    :param poll_timeout: (default=None)
        A timeout in seconds. If poll_timer has not been updated in poll_timeout seconds
        the thread is considered stuck and is restarted
    :param poll_target: (default=None)
        A callable which is called when a timeout occurs.
    :param thread_store_category: (default=None)
        Thread will be stored in a RestartableThread.thread_store with
        thread_store_category as key.
    :param register: (default=True)
        If true, threads will be registered in the ThreadWatchDog and automatically
        restart incase of an exception.
    """

    thread_store: Dict[str, List[threading.Thread]] = {}

    def __init__(
        self,
        group=None,
        target=None,
        name=None,
        args=(),
        kwargs=None,
        *,
        daemon=None,
        stop_target=None,
        poll_timer: Optional[List[float]] = None,
        poll_timeout=None,
        poll_target=None,
        thread_store_category=None,
        register=True
    ):
        super().__init__(
            group=group,
            target=target,
            name=name,
            args=args,
            kwargs=kwargs,
            daemon=daemon,
        )

        self._restartable_group = group
        self._restartable_target = target
        self._restartable_name = name
        self._restartable_args = args
        self._restartable_kwargs = None
        self._restartable_daemon = daemon
        self._stop_target = stop_target
        if any([poll_timer, poll_timeout, poll_target]) and not all(
            [poll_timer, poll_timeout, poll_target]
        ):
            LOGGER.error("poll_timer, poll_timeout, poll_target are mutually inclusive")
        if poll_timer:
            if not isinstance(poll_timer, list) and len(poll_timer) != 1:
                LOGGER.error(
                    "poll_timer needs to be a list with a single element "
                    "to keep it mutable"
                )
        self._poll_timer = poll_timer
        self._poll_timeout = poll_timeout
        self._poll_target = poll_target
        self._thread_store_category = thread_store_category
        if thread_store_category:
            self.thread_store.setdefault(thread_store_category, []).append(self)
        self._register = register
        if register:
            ThreadWatchDog.register(self)

    @property
    def started(self):
        """Return if thread has started."""
        return self._started.is_set()

    @property
    def poll_timer(self):
        """Return if thread has started."""
        return self._poll_timer

    @property
    def poll_timeout(self) -> Optional[int]:
        """Return max duration of inactivity for poll timer."""
        return self._poll_timeout

    @property
    def poll_target(self) -> Optional[Callable]:
        """Return target poll method."""
        return self._poll_target

    @property
    def thread_store_category(self) -> Optional[str]:
        """Return given thread store category."""
        return self._thread_store_category

    def stop(self) -> bool:
        """Calls given stop target method."""
        if self._thread_store_category:
            self.thread_store[self._thread_store_category].remove(self)
        if self._register:
            ThreadWatchDog.unregister(self)
        return self._stop_target() if self._stop_target else True

    def clone(self):
        """Return a clone of the thread to restart it."""
        return RestartableThread(
            group=self._restartable_group,
            target=self._restartable_target,
            name=self._restartable_name,
            args=self._restartable_args,
            kwargs=self._restartable_kwargs,
            daemon=self._restartable_daemon,
            stop_target=self._stop_target,
            poll_timer=self._poll_timer,
            poll_timeout=self._poll_timeout,
            poll_target=self._poll_target,
            thread_store_category=self._thread_store_category,
            register=False,
        )


class ThreadWatchDog:
    """A watchdog for long running threads."""

    registered_threads: List[RestartableThread] = []

    def __init__(self):
        self._scheduler = BackgroundScheduler(timezone="UTC", daemon=True)
        self._scheduler.add_job(self.watchdog, "interval", seconds=30)
        self._scheduler.start()

    @classmethod
    def register(
        cls,
        thread: RestartableThread,
    ):
        """Register a thread in the watchdog."""
        cls.registered_threads.append(thread)

    @classmethod
    def unregister(
        cls,
        thread: RestartableThread,
    ):
        """Unregister a thread in the watchdog."""
        cls.registered_threads.remove(thread)

    def watchdog(self):
        """Check for stopped threads and restart them."""
        for index, registered_thread in enumerate(self.registered_threads):
            if not registered_thread.started:
                continue

            if registered_thread.poll_timer and registered_thread.poll_timer[0]:
                now = datetime.datetime.now().timestamp()
                if (
                    now - registered_thread.poll_timer[0]
                    > registered_thread.poll_timeout
                ):
                    LOGGER.debug("Thread {} is stuck".format(registered_thread.name))
                    registered_thread.poll_target()
                    registered_thread.join()
                else:
                    continue
            elif registered_thread.is_alive():
                continue

            LOGGER.debug("Thread {} is dead, restarting".format(registered_thread.name))
            if registered_thread.thread_store_category:
                RestartableThread.thread_store[
                    registered_thread.thread_store_category
                ].remove(registered_thread)
            self.registered_threads[index] = registered_thread.clone()
            self.registered_threads[index].start()

    def stop(self):
        """Stop the watchdog."""
        self._scheduler.shutdown()
