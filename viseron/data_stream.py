"""Used to publish/subscribe to data between different parts of Viseron."""
import fnmatch
import logging
import uuid
from queue import Queue
from threading import Thread
from typing import Any, Callable, Dict, Union

from tornado.ioloop import IOLoop
from tornado.queues import Queue as tornado_queue

from viseron.helpers import pop_if_full

LOGGER = logging.getLogger(__name__)


class DataStream:
    """Class that enables a publisher/subscriber mechanism.
    Used to pass around frames and events between different components.

    A data topic can have any value.
    You can subscribe to wildcard topics using '*', eg topic/*/event_name

    Data is published to topics using a thread."""

    _subscribers: Dict[str, Any] = {}
    _wildcard_subscribers: Dict[str, Any] = {}
    _data_queue: Queue = Queue(maxsize=100)

    def __init__(self, ioloop: IOLoop) -> None:
        data_consumer = Thread(target=self.consume_data)
        data_consumer.start()
        self.ioloop = ioloop

    @staticmethod
    def publish_data(data_topic: str, data: Any) -> None:
        """Publish data to topic."""
        # LOGGER.debug(f"Publishing to data topic {data_topic}, {data}")
        DataStream._data_queue.put({"data_topic": data_topic, "data": data})

    @staticmethod
    def subscribe_data(
        data_topic: str, callback: Union[Callable, Queue, tornado_queue]
    ) -> uuid.UUID:
        """Subscribe to data on a topic.
        Returns a Unique ID which can be used to unsubscribe later."""
        LOGGER.debug(f"Subscribing to data topic {data_topic}, {callback}")
        unique_id = uuid.uuid4()

        if "*" in data_topic:
            DataStream._wildcard_subscribers.setdefault(data_topic, {})[
                unique_id
            ] = callback
            return unique_id

        DataStream._subscribers.setdefault(data_topic, {})[unique_id] = callback
        return unique_id

    @staticmethod
    def unsubscribe_data(data_topic: str, unique_id: uuid.UUID) -> None:
        """Unsubscribe from a topic using the Unique ID returned from subscribe_data."""
        LOGGER.debug(f"Unsubscribing from data topic {data_topic}, {unique_id}")
        if "*" in data_topic:
            DataStream._wildcard_subscribers[data_topic].pop(unique_id)
            return

        DataStream._subscribers[data_topic].pop(unique_id)

    def run_callbacks(
        self,
        callbacks: Dict[uuid.UUID, Union[Callable, Queue, tornado_queue]],
        data: Any,
    ) -> None:
        """Run callbacks or put to queues."""
        for callback in callbacks.values():
            if callable(callback):
                thread = Thread(target=callback, args=(data,))
                thread.daemon = True
                thread.start()
                continue

            if isinstance(callback, Queue):
                pop_if_full(callback, data)
                continue

            if isinstance(callback, tornado_queue):
                self.ioloop.add_callback(pop_if_full, callback, data)
                continue

            LOGGER.error(
                f"Callback {callback} is not valid. "
                f"Needs to be of type Callable or Queue, got {type(callback)}"
            )

    def static_subscriptions(self, data_item: Dict[str, Any]) -> None:
        """Run callbacks for static subscriptions."""
        self.run_callbacks(
            DataStream._subscribers.get(data_item["data_topic"], {}), data_item["data"]
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
