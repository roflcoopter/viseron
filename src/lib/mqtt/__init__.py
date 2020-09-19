import logging

import paho.mqtt.client as mqtt
from lib.nvr import FFMPEGNVR

LOGGER = logging.getLogger(__name__)


class MQTT:
    def __init__(self, config):
        LOGGER.info("Initializing MQTT connection")
        self.config = config
        self.client = None
        self.subscriptions = []

    # pylint: disable=unused-argument
    def on_connect(self, client, userdata, flags, returncode):
        LOGGER.debug("MQTT connected with result code {}".format(str(returncode)))

        self.subscriptions = {}
        for nvr in FFMPEGNVR.nvr_list:
            for name in list(nvr):
                subscriptions = nvr[name].on_connect(client)
                self.subscribe(subscriptions)

        # Send initial alive message
        client.publish(self.config.mqtt.last_will_topic, payload="alive", retain=True)

    def on_message(self, client, userdata, msg):
        LOGGER.debug(f"Got topic {msg.topic}, message {str(msg.payload.decode())}")
        for callback in self.subscriptions[msg.topic]:
            callback(msg)

    def connect(self):
        self.client = mqtt.Client(self.config.mqtt.client_id)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.enable_logger(logger=logging.getLogger("lib.mqtt_client"))
        logging.getLogger("lib.mqtt_client").setLevel(logging.INFO)
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
        for topic, _ in subscription.items():
            self.client.subscribe(topic)

        self.subscriptions.update(subscription)

    def publisher(self, mqtt_queue):
        while True:
            message = mqtt_queue.get()
            self.client.publish(
                message["topic"], payload=message["payload"], retain=True
            )
