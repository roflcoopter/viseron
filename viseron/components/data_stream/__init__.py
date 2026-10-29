"""Used to publish/subscribe to data between different parts of Viseron."""

from __future__ import annotations

import logging
import time
import uuid
from queue import Empty, Full, Queue
from typing import TYPE_CHECKING, Any

from viseron.components.data_stream.const import (
    COMPONENT,
    DATA_QUEUE_MAXSIZE,
    DROP_WARNING_INTERVAL,
    PUBLISH_MAX_ATTEMPTS,
    SIGNAL_TOPIC_PREFIX,
)
from viseron.components.data_stream.delivery import Dispatcher
from viseron.components.data_stream.registry import SubscriberRegistry
from viseron.components.data_stream.subscriber import create_subscriber
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from collections.abc import Callable

    from tornado.ioloop import IOLoop
    from tornado.queues import Queue as TornadoQueue

__all__ = ["COMPONENT", "DataStream", "setup"]

LOGGER = logging.getLogger(__name__)


def setup(vis, _) -> bool:
    """Set up the data_stream component."""
    vis.data[COMPONENT] = DataStream(vis)
    return True


class DataStream:
    """Class that enables a publisher/subscriber mechanism.

    Used to pass around frames and events between different components.

    A data topic can have any value.
    You can subscribe to wildcard topics using '*', eg topic/*/event_name

    Data is published to topics using a thread. A single consumer thread looks
    up subscribers and hands the data off, so it never blocks on subscriber
    work. Callback subscribers are delivered to on a shared pool, in publish
    order per subscriber.
    """

    _registry: SubscriberRegistry = SubscriberRegistry()
    _data_queue: Queue = Queue(maxsize=DATA_QUEUE_MAXSIZE)
    # Signals must never be dropped, so they bypass the bounded data queue.
    _signal_queue: Queue = Queue()

    _dropped_count: int = 0
    _last_drop_warning: float = 0.0

    def __init__(self, vis) -> None:
        self._vis = vis
        self._kill_received = False
        self._dispatcher = Dispatcher()
        self._data_consumer = RestartableThread(
            name="data_stream", target=self.consume_data, daemon=True, register=True
        )
        self._data_consumer.start()

    @staticmethod
    def publish_data(data_topic: str, data: Any = None) -> None:
        """Publish data to topic."""
        item = {"data_topic": data_topic, "data": data}

        if data_topic.startswith(SIGNAL_TOPIC_PREFIX):
            DataStream._signal_queue.put(item)
            return

        for _ in range(PUBLISH_MAX_ATTEMPTS):
            try:
                DataStream._data_queue.put_nowait(item)
                return
            except Full:
                try:
                    DataStream._data_queue.get_nowait()
                except Empty:
                    pass
                DataStream._record_drop()

        LOGGER.warning(f"Failed to publish to data topic {data_topic}, discarding")

    @staticmethod
    def _record_drop() -> None:
        """Count a dropped message and warn at most once per interval."""
        DataStream._dropped_count += 1
        now = time.time()
        if now - DataStream._last_drop_warning < DROP_WARNING_INTERVAL:
            return
        DataStream._last_drop_warning = now
        LOGGER.warning(
            "data_stream queue is full, dropped %s messages so far. "
            "A subscriber is not keeping up",
            DataStream._dropped_count,
        )

    @staticmethod
    def subscribe_data(
        data_topic: str,
        callback: Callable | Queue | TornadoQueue,
        ioloop: IOLoop | None = None,
        stage: str | None = None,
    ) -> uuid.UUID:
        """Subscribe to data on a topic.

        Returns a Unique ID which can be used to unsubscribe later.

        Raises:
            ValueError: If the callback can never be delivered to.
        """
        LOGGER.debug("Subscribing to data topic %s, %s", data_topic, callback)
        unique_id = uuid.uuid4()
        DataStream._registry.add(
            create_subscriber(unique_id, data_topic, callback, ioloop, stage)
        )
        return unique_id

    @staticmethod
    def unsubscribe_data(data_topic: str, unique_id: uuid.UUID) -> None:
        """Unsubscribe from a topic using the Unique ID returned from subscribe_data."""
        LOGGER.debug("Unsubscribing from data topic %s, %s", data_topic, unique_id)
        DataStream._registry.remove(data_topic, unique_id)

    @staticmethod
    def remove_all_subscriptions() -> None:
        """Remove all subscriptions."""
        DataStream._registry.clear()

    def run_callbacks(self, subscribers, data: Any) -> None:
        """Deliver data to every given subscriber."""
        for subscriber in subscribers:
            self._dispatcher.deliver(subscriber, data)

    def static_subscriptions(self, data_item: dict[str, Any]) -> None:
        """Run callbacks for static subscriptions."""
        self.run_callbacks(
            DataStream._registry.static_subscribers(data_item["data_topic"]),
            data_item["data"],
        )

    def wildcard_subscriptions(self, data_item: dict[str, Any]) -> None:
        """Run callbacks for wildcard subscriptions."""
        self.run_callbacks(
            DataStream._registry.wildcard_subscribers(data_item["data_topic"]),
            data_item["data"],
        )

    def _dispatch(self, data_item: dict[str, Any]) -> None:
        self.static_subscriptions(data_item)
        self.wildcard_subscriptions(data_item)

    def _drain_signals(self) -> None:
        """Handle every pending signal before any queued data."""
        while not DataStream._signal_queue.empty():
            try:
                self._dispatch(DataStream._signal_queue.get_nowait())
            except Empty:
                return

    def consume_data(self) -> None:
        """Publish data to topics."""
        while not self._kill_received:
            self._drain_signals()
            try:
                data_item = self._data_queue.get(timeout=0.1)
            except Empty:
                continue

            self._dispatch(data_item)

        self._drain_signals()
        LOGGER.debug("Data stream stopped")

    def join(self) -> None:
        """Join the data stream."""
        self._data_consumer.join()
        self._dispatcher.shutdown()

    def stop(self) -> None:
        """Stop the data stream."""
        self._kill_received = True
