"""Delivery of published data to subscribers."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, cast

from viseron.components.data_stream.const import (
    CALLBACK_WORKERS,
    DROP_WARNING_INTERVAL,
    SUBSCRIBER_QUEUE_MAXSIZE,
)
from viseron.components.data_stream.subscriber import SubscriberKind, describe
from viseron.helpers import pop_if_full
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from collections.abc import Callable

    from tornado.ioloop import IOLoop

    from viseron.components.data_stream.subscriber import Subscriber

LOGGER = logging.getLogger(__name__)


class SerialDelivery:
    """Deliver one subscriber's messages in publish order on a shared pool.

    The backlog is bounded, so a subscriber that cannot keep up drops its own
    oldest messages rather than stalling the bus for everyone else.
    """

    __slots__ = (
        "_backlog",
        "_dropped",
        "_executor",
        "_invoke",
        "_last_warning",
        "_lock",
        "_maxsize",
        "_running",
        "_subscriber",
    )

    def __init__(
        self,
        executor: ThreadPoolExecutor,
        subscriber: Subscriber,
        invoke: Callable[[Subscriber, Any], None],
        maxsize: int = SUBSCRIBER_QUEUE_MAXSIZE,
    ) -> None:
        self._executor = executor
        self._subscriber = subscriber
        self._invoke = invoke
        self._maxsize = maxsize
        self._backlog: deque[Any] = deque(maxlen=maxsize)
        self._lock = threading.Lock()
        self._running = False
        self._dropped = 0
        self._last_warning = 0.0

    def submit(self, data: Any) -> None:
        """Queue data for delivery, starting a drain task if one is not running."""
        with self._lock:
            if len(self._backlog) == self._maxsize:
                self._dropped += 1
                self._warn_dropped()
            self._backlog.append(data)
            if self._running:
                return
            self._running = True

        try:
            self._executor.submit(self._drain)
        except RuntimeError:  # Executor already shut down
            with self._lock:
                self._running = False

    def _warn_dropped(self) -> None:
        """Warn about a saturated backlog, at most once per interval."""
        now = time.time()
        if now - self._last_warning < DROP_WARNING_INTERVAL:
            return
        self._last_warning = now
        LOGGER.warning(
            "Subscriber %s on data topic %s is too slow, dropped %s messages so far",
            describe(self._subscriber),
            self._subscriber.data_topic,
            self._dropped,
        )

    def _drain(self) -> None:
        while True:
            with self._lock:
                if not self._backlog:
                    self._running = False
                    return
                data = self._backlog.popleft()

            try:
                self._invoke(self._subscriber, data)
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception(
                    f"Error in subscriber {describe(self._subscriber)} "
                    f"on data topic {self._subscriber.data_topic}"
                )


class Dispatcher:
    """Route published data to a subscriber using its resolved delivery kind."""

    def __init__(self, workers: int = CALLBACK_WORKERS) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="data_stream_callback"
        )

    def deliver(self, subscriber: Subscriber, data: Any) -> None:
        """Deliver data to a single subscriber."""
        kind = subscriber.kind

        if kind is SubscriberKind.QUEUE:
            pop_if_full(subscriber.callback, data)  # type: ignore[arg-type]
            return

        if kind is SubscriberKind.TORNADO_QUEUE:
            ioloop = cast("IOLoop", subscriber.ioloop)
            ioloop.add_callback(pop_if_full, subscriber.callback, data)
            return

        if kind in (SubscriberKind.IOLOOP_CALLBACK, SubscriberKind.IOLOOP_COROUTINE):
            ioloop = cast("IOLoop", subscriber.ioloop)
            ioloop.add_callback(run_in_ioloop, subscriber, data)
            return

        if kind is SubscriberKind.SIGNAL_CALLBACK:
            self._run_in_signal_thread(subscriber, data)
            return

        if subscriber.delivery is None:
            subscriber.delivery = SerialDelivery(
                self._executor, subscriber, _invoke_callback
            )
        subscriber.delivery.submit(data)

    @staticmethod
    def _run_in_signal_thread(subscriber: Subscriber, data: Any) -> None:
        """Run a signal handler in its own non-daemon thread.

        Viseron.shutdown enumerates live threads and joins the ones tagged with
        the stage it is currently draining, so these must not share the pool.
        """
        args = () if data is None else (data,)
        thread = RestartableThread(
            name=subscriber.thread_name,
            target=subscriber.callback,
            args=args,
            daemon=False,
            register=False,
            stage=subscriber.stage,
        )
        thread.start()

    def shutdown(self) -> None:
        """Stop accepting new callback deliveries."""
        self._executor.shutdown(wait=False)


def _invoke_callback(subscriber: Subscriber, data: Any) -> None:
    """Call a plain callable subscriber."""
    if data is None:
        subscriber.callback()  # type: ignore[operator]
        return
    subscriber.callback(data)  # type: ignore[operator]


async def run_in_ioloop(subscriber: Subscriber, data: Any) -> None:
    """Run a callback on the subscriber's ioloop."""
    callback = subscriber.callback
    try:
        if subscriber.kind is SubscriberKind.IOLOOP_COROUTINE:
            if data is None:
                await callback()  # type: ignore[operator]
            else:
                await callback(data)  # type: ignore[operator]
            return

        def _wrapper() -> None:
            if data is None:
                callback()  # type: ignore[operator]
                return
            callback(data)  # type: ignore[operator]

        await cast("IOLoop", subscriber.ioloop).run_in_executor(None, _wrapper)
    except Exception:  # pylint: disable=broad-except
        LOGGER.exception(
            f"Error in subscriber {describe(subscriber)} "
            f"on data topic {subscriber.data_topic}"
        )
