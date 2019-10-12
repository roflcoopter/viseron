import paho.mqtt.client as mqtt
from datetime import datetime
from lib.nvr import FFMPEGNVR
import logging
import config
import json
import cv2

LOGGER = logging.getLogger(__name__)

MQTT_SWITCH_CONFIG = "%s/switch/%s/config" % (config.MQTT_PREFIX, config.MQTT_TOPIC)
MQTT_SWITCH_CMD = "%s/switch/%s/set" % (config.MQTT_PREFIX, config.MQTT_TOPIC)
MQTT_SWITCH_STATE = "%s/switch/%s/state" % (config.MQTT_PREFIX, config.MQTT_TOPIC)

MQTT_SENSOR_CONFIG = "%s/sensor/%s/config" % (config.MQTT_PREFIX, config.MQTT_TOPIC)
MQTT_SENSOR_AVAILABILITY = "%s/sensor/%s/lwt" % (config.MQTT_PREFIX, config.MQTT_TOPIC)
MQTT_SENSOR_STATE = "%s/sensor/%s/state" % (config.MQTT_PREFIX, config.MQTT_TOPIC)

MQTT_CAMERA_CONFIG = "%s/camera/%s/config" % (config.MQTT_PREFIX, config.MQTT_TOPIC)
MQTT_CAMERA_IMAGE = "%s/camera/%s/image" % (config.MQTT_PREFIX, config.MQTT_TOPIC)


class MQTT:
    def __init__(self, config):
        LOGGER.info("Initializing MQTT connection")
        self.config = config

    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(client, userdata, flags, rc):
        LOGGER.info("MQTT connected with result code {}".format(str(rc)))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.

        LOGGER.info("HELLOOOOOOOO")
        LOGGER.info(FFMPEGNVR.nvr_list)
        for nvr in FFMPEGNVR.nvr_list:
            for x in list(nvr):
                try:
                    nvr[x].on_connect(client)
                except Exception as e:
                    LOGGER.error(e)
        client.subscribe(MQTT_SWITCH_CMD)

        # Sensor config message
        payload = {}
        payload["name"] = config.MQTT_TOPIC
        payload["state_topic"] = MQTT_SENSOR_STATE
        payload["value_template"] = "{{ value_json.state }}"
        payload["availability_topic"] = MQTT_SENSOR_AVAILABILITY
        payload["payload_available"] = "alive"
        payload["payload_not_available"] = "dead"
        payload["json_attributes_topic"] = MQTT_SENSOR_STATE
        json_payload = json.dumps(payload, indent=3)
        client.publish(MQTT_SENSOR_CONFIG, payload=json_payload, retain=True)

        # Camera config message
        payload = {}
        payload["name"] = config.MQTT_TOPIC
        payload["topic"] = MQTT_CAMERA_IMAGE
        json_payload = json.dumps(payload, indent=3)
        client.publish(MQTT_CAMERA_CONFIG, payload=json_payload, retain=False)

        # Send initial alive message
        client.publish(MQTT_SENSOR_AVAILABILITY, payload="alive", retain=True)
        # Send initial off message
        client.publish(MQTT_SENSOR_STATE, payload='{"state": "off"}', retain=True)

    # The callback for when a PUBLISH message is received from the server.
    def on_message(client, userdata, msg):
        #    LOGGER.info('Acknowledge state {}'.format(str(msg.payload.decode())))
        client.publish(
            MQTT_SWITCH_STATE, payload=str(msg.payload.decode()), retain=True
        )

    # The callback for when a PUBLISH message is sent to the server.
    #  def on_publish(client, userdata, msg):
    #      LOGGER.info(msg)

    def connect(self):
        self.client = mqtt.Client("viseron")
        self.client.on_connect = MQTT.on_connect
        self.client.on_message = MQTT.on_message
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

    def publish_sensor(self, object_detected, detections):
        payload = {}
        payload["state"] = "on" if object_detected else "off"
        payload["detections"] = detections
        payload["timestamp"] = str(datetime.now())
        json_payload = json.dumps(payload, indent=3)

        self.client.publish(MQTT_SENSOR_STATE, payload=json_payload, retain=True)

    def publish_image(self, frame):
        ret, jpg = cv2.imencode(".jpg", frame)
        if ret:
            jpg_bytes = jpg.tobytes()
            self.client.publish(MQTT_CAMERA_IMAGE, jpg_bytes, retain=True)
