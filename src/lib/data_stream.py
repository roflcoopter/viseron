import fnmatch
import logging
from queue import Queue
from threading import Thread
from typing import Any, Callable, Dict, Union

from lib.helpers import pop_if_full

LOGGER = logging.getLogger(__name__)


class DataStream:
    """ Class that enables a publisher/subscriber mechanism.
    Used to pass around frames and events between different components.

    A data topic can have any value.
    You can subscribe to wildcard topics using '*', eg topic/*/event_name
    """

    _subscribers: Dict[str, Any] = {}
    _wildcard_subscribers: Dict[str, Any] = {}
    _data_queue: Queue = Queue(maxsize=100)

    def __init__(self):
        data_consumer = Thread(target=self.consume_data)
        data_consumer.start()

    @staticmethod
    def publish_data(data_topic, data):
        LOGGER.debug(f"Publishing to data topic {data_topic}, {data}")
        DataStream._data_queue.put({"data_topic": data_topic, "data": data})

    @staticmethod
    def subscribe_data(data_topic, callback: Union[Callable, Queue]):
        LOGGER.debug(f"Subscribing to data topic {data_topic}, {callback}")
        if "*" in data_topic:
            DataStream._wildcard_subscribers.setdefault(data_topic, []).append(callback)
            return

        DataStream._subscribers.setdefault(data_topic, []).append(callback)

    @staticmethod
    def run_callbacks(callbacks, data_item):
        for callback in callbacks:
            if callable(callback):
                thread = Thread(target=callback, args=(data_item["data"],))
                thread.daemon = True
                thread.start()
                continue

            if isinstance(callback, Queue):
                pop_if_full(callback, data_item["data"])
                continue

            LOGGER.error(
                f"Callback {callback} is not valid. "
                f"Needs to be of type Callable or Queue, got {type(callback)}"
            )

    def static_subscriptions(self, data_item):
        self.run_callbacks(
            self._subscribers.get(data_item["data_topic"], []), data_item
        )

    def wildcard_subscriptions(self, data_item):
        for data_topic, callbacks in self._wildcard_subscribers.items():
            if fnmatch.fnmatch(data_item["data_topic"], data_topic):
                LOGGER.debug(
                    f"Got data on topic {data_item['data_topic']} "
                    f"matching with subscriber on topic {data_topic}"
                )

                self.run_callbacks(callbacks, data_item)

    def consume_data(self):
        while True:
            data_item = self._data_queue.get()
            self.static_subscriptions(data_item)
            self.wildcard_subscriptions(data_item)
