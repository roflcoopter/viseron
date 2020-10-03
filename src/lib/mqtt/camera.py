import json

import logging

LOGGER = logging.getLogger(__name__)


class MQTTCamera:
    def __init__(self, config, mqtt_queue):
        self._config = config
        self._mqtt_queue = mqtt_queue
        self._name = config.camera.mqtt_name
        self._device_name = f"{config.mqtt.client_id} {config.camera.name}"
        self._unique_id = self.name

    @property
    def base_topic(self):
        return f"{self._config.mqtt.discovery_prefix}/camera/" f"{self.name}"

    @property
    def state_topic(self):
        return f"{self.base_topic}/image"

    @property
    def config_topic(self):
        return f"{self.base_topic}/config"

    @property
    def name(self):
        return self._name

    @property
    def device_name(self):
        return self._device_name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def device_info(self):
        return {
            "identifiers": [self.device_name],
            "name": self.device_name,
            "manufacturer": "Viseron",
        }

    @property
    def config_payload(self):
        payload = {}
        payload["name"] = self.name
        payload["unique_id"] = self.unique_id
        payload["topic"] = self.state_topic
        payload["availability_topic"] = self._config.mqtt.last_will_topic
        payload["payload_available"] = "alive"
        payload["payload_not_available"] = "dead"
        payload["device"] = self.device_info
        return json.dumps(payload, indent=3)

    def on_connect(self, client):
        client.publish(
            self.config_topic, payload=self.config_payload, retain=True,
        )
        client.publish(self.state_topic, payload="off")

    def publish(self, image):
        self._mqtt_queue.put({"topic": self.state_topic, "payload": image})
