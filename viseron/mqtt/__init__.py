"""MQTT interface."""
import logging

import paho.mqtt.client as mqtt

from viseron.nvr import FFMPEGNVR
from viseron.post_processors import PostProcessor

LOGGER = logging.getLogger(__name__)

MQTT_RC = {
    0: "Connection successful",
    1: "Connection refused - incorrect protocol version",
    2: "Connection refused - invalid client identifier",
    3: "Connection refused - server unavailable",
    4: "Connection refused - bad username or password",
    5: "Connection refused - not authorised",
}


class MQTT:
    """MQTT interface."""

    def __init__(self, config):
        LOGGER.info("Initializing MQTT connection")
        self.config = config
        self.client = None
        self.subscriptions = []

    # pylint: disable=unused-argument
    def on_connect(self, client, userdata, flags, returncode):
        """Called when MQTT connection is established.
        Calls on_connect methods in all dependant components."""
        LOGGER.debug(f"MQTT connected with returncode {str(returncode)}")
        if returncode != 0:
            LOGGER.error(
                f"Could not connect to broker. Returncode: {returncode}: "
                f"{MQTT_RC.get(returncode, 'Unknown error')}"
            )

        self.subscriptions = {}
        for nvr in FFMPEGNVR.nvr_list.values():
            subscriptions = nvr.on_connect(client)
            self.subscribe(subscriptions)

        for post_processor in PostProcessor.post_processor_list:
            post_processor.on_connect(client)

        # Send initial alive message
        client.publish(self.config.mqtt.last_will_topic, payload="alive", retain=True)

    def on_message(self, client, userdata, msg):
        """Called on receiving a message."""
        LOGGER.debug(f"Got topic {msg.topic}, message {str(msg.payload.decode())}")
        for callback in self.subscriptions[msg.topic]:
            callback(msg)

    def connect(self):
        """Connect to broker."""
        self.client = mqtt.Client(self.config.mqtt.client_id)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.enable_logger(logger=logging.getLogger("viseron.mqtt_client"))
        logging.getLogger("viseron.mqtt_client").setLevel(logging.INFO)
        if self.config.mqtt.username:
            self.client.username_pw_set(
                self.config.mqtt.username, self.config.mqtt.password
            )

        # Set a Last Will message
        self.client.will_set(
            self.config.mqtt.last_will_topic, payload="dead", retain=True
        )
        self.client.connect(self.config.mqtt.broker, self.config.mqtt.port, 10)

        # Start threaded loop to read/publish messages
        self.client.loop_start()

    def subscribe(self, subscription):
        """Subscribe to a topic."""
        for topic, _ in subscription.items():
            self.client.subscribe(topic)

        self.subscriptions.update(subscription)

    def publisher(self, mqtt_queue):
        """Publishing thread."""
        while True:
            message = mqtt_queue.get()
            self.client.publish(
                message["topic"], payload=message["payload"], retain=True
            )
