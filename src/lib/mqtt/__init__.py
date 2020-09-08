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

        self.subscriptions = []
        for nvr in FFMPEGNVR.nvr_list:
            for name in list(nvr):
                subscriptions = nvr[name].on_connect(client)
                for subscription in subscriptions:
                    client.subscribe(subscription["topic"])
                    self.subscriptions.append(subscription)

        # Send initial alive message
        client.publish(self.config.mqtt.last_will_topic, payload="alive", retain=True)

    def on_message(self, client, userdata, msg):
        LOGGER.debug("Acknowledge state {}".format(str(msg.payload.decode())))
        for subscription in self.subscriptions:
            if subscription["topic"] == msg.topic:
                subscription["callback"](msg)

    def connect(self):
        self.client = mqtt.Client(self.config.mqtt.client_id)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        #    self.client.on_publish = MQTT.on_publish
        self.client.enable_logger(logger=logging.getLogger("lib.mqtt"))
        logging.getLogger("lib.mqtt").setLevel(logging.INFO)
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

    def publisher(self, mqtt_queue):
        while True:
            message = mqtt_queue.get()
            self.client.publish(
                message["topic"], payload=message["payload"], retain=True
            )
