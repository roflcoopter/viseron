"""MQTT interface."""
import logging
from dataclasses import dataclass
from queue import Queue
from typing import Any, Callable, Dict, List

import paho.mqtt.client as mqtt

LOGGER = logging.getLogger(__name__)

MQTT_RC = {
    0: "Connection successful",
    1: "Connection refused - incorrect protocol version",
    2: "Connection refused - invalid client identifier",
    3: "Connection refused - server unavailable",
    4: "Connection refused - bad username or password",
    5: "Connection refused - not authorised",
}


@dataclass
class PublishPayload:
    """Payload to publish to MQTT."""

    topic: str
    payload: Any
    retain: bool = False


@dataclass
class SubscribeTopic:
    """Subscribe to a topic."""

    topic: str
    callback: Callable


class MQTT:
    """MQTT interface."""

    client: mqtt.Client = None
    publish_queue: Queue = Queue(maxsize=1000)
    subscriptions: Dict[str, List[Callable]] = {}

    def __init__(self, config):
        LOGGER.info("Initializing MQTT connection")
        self.config = config

    def on_connect(self, client, _userdata, _flags, returncode):
        """On established MQTT connection.

        Calls on_connect methods in all dependent components.
        """
        LOGGER.debug(f"MQTT connected with returncode {str(returncode)}")
        if returncode != 0:
            LOGGER.error(
                f"Could not connect to broker. Returncode: {returncode}: "
                f"{MQTT_RC.get(returncode, 'Unknown error')}"
            )

        # Send initial alive message
        client.publish(self.config.mqtt.last_will_topic, payload="alive", retain=True)

    def on_message(self, _client, _userdata, msg):
        """On message received."""
        LOGGER.debug(f"Got topic {msg.topic}, message {str(msg.payload.decode())}")
        for callback in self.subscriptions[msg.topic]:
            callback(msg)

    def connect(self):
        """Connect to broker."""
        MQTT.client = mqtt.Client(self.config.mqtt.client_id)
        MQTT.client.on_connect = self.on_connect
        MQTT.client.on_message = self.on_message
        MQTT.client.enable_logger(logger=logging.getLogger("viseron.mqtt_client"))
        logging.getLogger("viseron.mqtt_client").setLevel(logging.INFO)
        if self.config.mqtt.username:
            MQTT.client.username_pw_set(
                self.config.mqtt.username, self.config.mqtt.password
            )

        # Set a Last Will message
        MQTT.client.will_set(
            self.config.mqtt.last_will_topic, payload="dead", retain=True
        )
        MQTT.client.connect(self.config.mqtt.broker, self.config.mqtt.port, 10)

        # Start threaded loop to read/publish messages
        MQTT.client.loop_start()

    @classmethod
    def subscribe(cls, subscription: SubscribeTopic):
        """Subscribe to a topic."""
        if subscription.topic not in cls.subscriptions:
            cls.client.subscribe(subscription.topic)

        cls.subscriptions.setdefault(subscription.topic, [])
        cls.subscriptions[subscription.topic].append(subscription.callback)

    @classmethod
    def publish(cls, payload: PublishPayload):
        """Put payload in publish queue."""
        if cls.client:
            cls.publish_queue.put(payload)
        else:
            LOGGER.error("Trying to publish when MQTT has not been initialized")

    @staticmethod
    def publisher():
        """Publish thread."""
        while True:
            message: PublishPayload = MQTT.publish_queue.get()
            MQTT.client.publish(
                message.topic,
                payload=message.payload,
                retain=message.retain,
            )
