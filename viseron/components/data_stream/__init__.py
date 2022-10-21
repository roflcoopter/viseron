"""Used to publish/subscribe to data between different parts of Viseron."""
from __future__ import annotations

import fnmatch
import logging
import multiprocessing as mp
import threading
import uuid
from queue import Queue
from typing import Any, Callable, Dict, TypedDict, Union

from tornado.ioloop import IOLoop
from tornado.queues import Queue as tornado_queue

from viseron import helpers
from viseron.watchdog.thread_watchdog import RestartableThread

COMPONENT = "data_stream"

LOGGER = logging.getLogger(__name__)


class DataSubscriber(TypedDict):
    """Data subscriber type."""

    callback: Union[Callable, Queue, tornado_queue]
    ioloop: Union[IOLoop, None]


class Subscribe(TypedDict):
    """Subscribe to data from process."""

    data_topic: str
    callback: Union[mp.Queue]


class Publish(TypedDict):
    """Data to publish from process."""

    data_topic: str
    data: Any


def setup(vis, _):
    """Set up the data_stream component."""
    vis.data[COMPONENT] = DataStream(vis)
    return True


class DataStream:
    """Class that enables a publisher/subscriber mechanism.

    Used to pass around frames and events between different components.

    A data topic can have any value.
    You can subscribe to wildcard topics using '*', eg topic/*/event_name

    Data is published to topics using a thread.
    """

    _subscribers: Dict[str, Any] = {}
    _wildcard_subscribers: Dict[str, Any] = {}
    _data_queue: Queue = Queue(maxsize=1000)

    def __init__(self, vis) -> None:
        self._vis = vis
        data_consumer = RestartableThread(
            name="data_stream", target=self.consume_data, daemon=True, register=True
        )
        data_consumer.start()

    @staticmethod
    def publish_data(data_topic: str, data: Any = None) -> None:
        """Publish data to topic."""
        # LOGGER.debug(f"Publishing to data topic {data_topic}, {data}")
        helpers.pop_if_full(
            DataStream._data_queue, {"data_topic": data_topic, "data": data}
        )

    @staticmethod
    def subscribe_data(
        data_topic: str, callback: Union[Callable, Queue, tornado_queue], ioloop=None
    ) -> uuid.UUID:
        """Subscribe to data on a topic.

        Returns a Unique ID which can be used to unsubscribe later.
        """
        LOGGER.debug(f"Subscribing to data topic {data_topic}, {callback}")
        unique_id = uuid.uuid4()

        if "*" in data_topic:
            DataStream._wildcard_subscribers.setdefault(data_topic, {})[
                unique_id
            ] = DataSubscriber(
                callback=callback,
                ioloop=ioloop,
            )
            return unique_id

        DataStream._subscribers.setdefault(data_topic, {})[unique_id] = DataSubscriber(
            callback=callback,
            ioloop=ioloop,
        )
        return unique_id

    @staticmethod
    def unsubscribe_data(data_topic: str, unique_id: uuid.UUID) -> None:
        """Unsubscribe from a topic using the Unique ID returned from subscribe_data."""
        LOGGER.debug(f"Unsubscribing from data topic {data_topic}, {unique_id}")
        if "*" in data_topic:
            DataStream._wildcard_subscribers[data_topic].pop(unique_id)
            return

        DataStream._subscribers[data_topic].pop(unique_id)

    @staticmethod
    def run_callbacks(
        callbacks: Dict[uuid.UUID, DataSubscriber],
        data: Any,
    ) -> None:
        """Run callbacks or put to queues."""
        for callback in callbacks.values():
            if callable(callback["callback"]) and callback["ioloop"] is None:
                if data:
                    thread = threading.Thread(
                        target=callback["callback"],
                        args=(data,),
                        daemon=True,
                    )
                else:
                    thread = threading.Thread(
                        target=callback["callback"],
                        daemon=True,
                    )
                thread.start()
                continue

            if callable(callback["callback"]) and callback["ioloop"] is not None:
                if data:
                    callback["ioloop"].add_callback(callback["callback"], data)
                else:
                    callback["ioloop"].add_callback(callback["callback"])
                continue

            if isinstance(callback["callback"], Queue):
                helpers.pop_if_full(callback["callback"], data)
                continue

            if callback["ioloop"] is not None and isinstance(
                callback["callback"], tornado_queue
            ):
                callback["ioloop"].add_callback(
                    helpers.pop_if_full, callback["callback"], data
                )
                continue

            LOGGER.error(
                f"Callback {callback} is not valid. "
                f"Needs to be of type Callable, Queue or "
                f"Tornado Queue with ioloop supplied, got {type(callback['callback'])}"
            )

    def static_subscriptions(self, data_item: Dict[str, Any]) -> None:
        """Run callbacks for static subscriptions."""
        self.run_callbacks(
            DataStream._subscribers.get(data_item["data_topic"], {}),
            data_item["data"],
        )

    def wildcard_subscriptions(self, data_item: Dict[str, Any]) -> None:
        """Run callbacks for wildcard subscriptions."""
        for data_topic, callbacks in DataStream._wildcard_subscribers.items():
            if fnmatch.fnmatch(data_item["data_topic"], data_topic):
                # LOGGER.debug(
                #     f"Got data on topic {data_item['data_topic']} "
                #     f"matching with subscriber on topic {data_topic}"
                # )

                self.run_callbacks(callbacks, data_item["data"])

    def consume_data(self) -> None:
        """Publish data to topics."""
        while True:
            data_item = self._data_queue.get()
            self.static_subscriptions(data_item)
            self.wildcard_subscriptions(data_item)
