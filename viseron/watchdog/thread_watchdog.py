"""Watchdog for long-running threads."""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, overload

from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.watchdog import WatchDog

if TYPE_CHECKING:
    from viseron import Viseron
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
        restart in case of an exception.
    """

    thread_store: dict[str, list[threading.Thread]] = {}

    @overload
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
        thread_store_category=None,
        register=True,
        restart_method: Callable | None = None,
        base_class=None,
        base_class_args=(),
        stage: str | None = VISERON_SIGNAL_SHUTDOWN,
    ) -> None:
        ...

    @overload
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
        poll_method: Callable,
        poll_target: Callable,
        thread_store_category=None,
        register=True,
        restart_method: Callable | None = None,
        base_class=None,
        base_class_args=(),
        stage: str | None = VISERON_SIGNAL_SHUTDOWN,
    ) -> None:
        ...

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
        poll_method=None,
        poll_target=None,
        thread_store_category=None,
        register=True,
        restart_method: Callable | None = None,
        base_class=None,
        base_class_args=(),
        stage: str | None = VISERON_SIGNAL_SHUTDOWN,
    ) -> None:
        # _started is set in Thread.__init__() but we set it here to make mypy happy
        self._started = threading.Event()
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
        self._poll_method = poll_method
        self._poll_target = poll_target
        self._thread_store_category = thread_store_category
        if thread_store_category:
            self.thread_store.setdefault(thread_store_category, []).append(self)
        if register:
            ThreadWatchDog.register(self)
        self._restart_method = restart_method
        self._base_class = base_class
        self._base_class_args = base_class_args
        self._stage = stage
        setattr(self, "__stage__", stage)

    @property
    def started(self):
        """Return if thread has started."""
        return self._started.is_set()

    @property
    def poll_method(self) -> Callable | None:
        """Return poll method."""
        return self._poll_method

    @property
    def poll_target(self) -> Callable | None:
        """Return poll target method."""
        return self._poll_target

    @property
    def restart_method(self) -> Callable | None:
        """Return restart method."""
        return self._restart_method

    @property
    def thread_store_category(self) -> str | None:
        """Return given thread store category."""
        return self._thread_store_category

    def stop(self) -> bool:
        """Call given stop target method."""
        LOGGER.debug(f"Stopping thread {self.name}")
        if self._thread_store_category:
            self.thread_store[self._thread_store_category].remove(self)
        ThreadWatchDog.unregister(self)
        return self._stop_target() if self._stop_target else True

    def clone(self):
        """Return a clone of the thread to restart it."""
        LOGGER.debug(f"Cloning thread {self.name}")
        if self._base_class:
            return self._base_class(*self._base_class_args, register=False)

        return RestartableThread(
            group=self._restartable_group,
            target=self._restartable_target,
            name=self._restartable_name,
            args=self._restartable_args,
            kwargs=self._restartable_kwargs,
            daemon=self._restartable_daemon,
            stop_target=self._stop_target,
            poll_method=self._poll_method,
            poll_target=self._poll_target,
            thread_store_category=self._thread_store_category,
            register=False,
            restart_method=self._restart_method,
            base_class=self._base_class,
            base_class_args=self._base_class_args,
            stage=self._stage,
        )


class ThreadWatchDog(WatchDog):
    """A watchdog for long running threads."""

    registered_items: list[RestartableThread] = []

    def __init__(self, vis: Viseron) -> None:
        super().__init__()
        vis.background_scheduler.add_job(
            self.watchdog,
            "interval",
            id="thread_watchdog",
            name="thread_watchdog",
            seconds=15,
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

    def watchdog(self) -> None:
        """Check for stopped threads and restart them."""
        new_threads: list[RestartableThread] = []
        deleted_threads: list[RestartableThread] = []
        registered_thread: RestartableThread
        for registered_thread in self.registered_items.copy():
            if not registered_thread.started:
                continue

            if (
                registered_thread.poll_method
                and registered_thread.poll_target
                and registered_thread.poll_method()
            ):
                LOGGER.debug(f"Thread {registered_thread.name} is stuck")
                registered_thread.poll_target()
                registered_thread.join(timeout=5)
                if registered_thread.is_alive():
                    LOGGER.error(
                        "Failed to stop thread. "
                        "Make sure poll_target ends the thread"
                    )
            elif registered_thread.is_alive():
                continue

            LOGGER.error(f"Thread {registered_thread.name} is dead, restarting")
            if registered_thread.thread_store_category:
                RestartableThread.thread_store[
                    registered_thread.thread_store_category
                ].remove(registered_thread)
            if registered_thread.restart_method:
                registered_thread.restart_method()
            else:
                new_thread = registered_thread.clone()
                if not new_thread.started:
                    new_thread.start()
                new_threads.append(new_thread)
                deleted_threads.append(registered_thread)

        for thread in new_threads:
            self.registered_items.append(thread)
        for thread in deleted_threads:
            self.registered_items.remove(thread)
