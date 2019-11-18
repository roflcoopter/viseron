import logging

import config
import paho.mqtt.client as mqtt
from lib.nvr import FFMPEGNVR

LOGGER = logging.getLogger(__name__)

MQTT_SENSOR_AVAILABILITY = "%s/sensor/%s/lwt" % (config.MQTT_PREFIX, config.MQTT_TOPIC)


class MQTT:
    def __init__(self, config):
        LOGGER.info("Initializing MQTT connection")
        self.config = config
        self.subscriptions = []

    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(self, client, userdata, flags, rc):
        LOGGER.info("MQTT connected with result code {}".format(str(rc)))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        self.subscriptions = []
        for nvr in FFMPEGNVR.nvr_list:
            for x in list(nvr):
                try:
                    subscriptions = nvr[x].on_connect(client)
                    for subscription in subscriptions:
                        client.subscribe(subscription["topic"])
                        self.subscriptions.append(subscription)
                except Exception as e:
                    LOGGER.error(e)

        # Send initial alive message
        # client.publish(MQTT_SENSOR_AVAILABILITY, payload="alive", retain=True)

    # The callback for when a PUBLISH message is received from the server.
    def on_message(self, client, userdata, msg):
        LOGGER.debug("Acknowledge state {}".format(str(msg.payload.decode())))
        for subscription in self.subscriptions:
            if subscription["topic"] == msg.topic:
                subscription["callback"](msg)

    # The callback for when a PUBLISH message is sent to the server.
    #  def on_publish(client, userdata, msg):
    #      LOGGER.info(msg)

    def connect(self):
        self.client = mqtt.Client("viseron")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        #    self.client.on_publish = MQTT.on_publish
        self.client.enable_logger(logger=logging.getLogger("lib.mqtt"))
        logging.getLogger("lib.mqtt").setLevel(logging.INFO)
        if config.MQTT_USERNAME:
            self.client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)

        # Set a Last Will message
        self.client.will_set(MQTT_SENSOR_AVAILABILITY, payload="dead", retain=True)
        self.client.connect(config.MQTT_BROKER, config.MQTT_PORT, 10)

        # Start threaded loop to read/publish messages
        self.client.loop_start()

    def publisher(self, mqtt_queue):
        while True:
            message = mqtt_queue.get()
            self.client.publish(
                message["topic"], payload=message["payload"], retain=True
            )
