import json

import logging

LOGGER = logging.getLogger(__name__)


class MQTTCamera:
    def __init__(self, config, mqtt_queue):
        self._config = config
        self._mqtt_queue = mqtt_queue

    @property
    def base_topic(self):
        return (
            f"{self._config.mqtt.discovery_prefix}/camera/"
            f"{self._config.camera.mqtt_name}"
        )

    @property
    def state_topic(self):
        return f"{self.base_topic}/image"

    @property
    def config_topic(self):
        return f"{self.base_topic}/config"

    @property
    def config_payload(self):
        payload = {}
        payload["name"] = self._config.camera.mqtt_name
        payload["topic"] = self.state_topic
        payload["availability_topic"] = self._config.mqtt.last_will_topic
        payload["payload_available"] = "alive"
        payload["payload_not_available"] = "dead"
        return json.dumps(payload, indent=3)

    def on_connect(self, client):
        client.publish(
            self.config_topic, payload=self.config_payload, retain=True,
        )
        client.publish(self.state_topic, payload="off")

    def publish(self, image):
        self._mqtt_queue.put({"topic": self.state_topic, "payload": image})
