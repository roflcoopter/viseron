import json
import logging

from lib.helpers import slugify

LOGGER = logging.getLogger(__name__)


class MQTTCamera:
    def __init__(self, config, mqtt_queue, object_id=""):
        self._config = config
        self._mqtt_queue = mqtt_queue
        self._object_id = object_id
        self._node_id = config.camera.mqtt_name
        self._name = config.camera.mqtt_name
        self._device_name = f"{config.mqtt.client_id} {config.camera.name}"
        self._unique_id = slugify(self.name)

    @property
    def state_topic(self):
        if self._object_id:
            return (
                f"{self._config.mqtt.client_id}/{self.node_id}/camera/"
                f"{self._object_id}/image"
            )
        return f"{self._config.mqtt.client_id}/{self.node_id}/camera/image"

    @property
    def config_topic(self):
        if self._object_id:
            return (
                f"{self._config.mqtt.home_assistant.discovery_prefix}/camera/"
                f"{self.node_id}/{self._object_id}/config"
            )
        return (
            f"{self._config.mqtt.home_assistant.discovery_prefix}/camera/"
            f"{self.node_id}/config"
        )

    @property
    def name(self):
        if self._object_id:
            return f"{self._name} {self._object_id}"
        return self._name

    @property
    def device_name(self):
        return self._device_name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def node_id(self):
        return self._node_id

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
        if self._config.mqtt.home_assistant.enable:
            client.publish(
                self.config_topic, payload=self.config_payload, retain=True,
            )

    def publish(self, image):
        self._mqtt_queue.put({"topic": self.state_topic, "payload": image})
