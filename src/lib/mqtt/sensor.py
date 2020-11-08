import json
from lib.helpers import slugify


class MQTTSensor:
    def __init__(self, config, mqtt_queue, name):
        self._config = config
        self._mqtt_queue = mqtt_queue
        self._name = f"{config.mqtt.client_id} {config.camera.name} {name}"
        self._device_name = f"{config.mqtt.client_id} {config.camera.name}"
        self._unique_id = slugify(self._name)
        self._node_id = self._config.camera.mqtt_name
        self._object_id = slugify(name)

    @property
    def state_topic(self):
        return (
            f"{self._config.mqtt.client_id}/{self._node_id}/"
            f"sensor/{self.object_id}/state"
        )

    @property
    def config_topic(self):
        return (
            f"{self._config.mqtt.home_assistant.discovery_prefix}/sensor/"
            f"{self.node_id}/{self.object_id}/config"
        )

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
    def node_id(self):
        return self._node_id

    @property
    def object_id(self):
        return self._object_id

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
        payload["name"] = self.name  # entitu_id
        payload["unique_id"] = self.unique_id
        payload["state_topic"] = self.state_topic
        payload["value_template"] = "{{ value_json.state }}"
        payload["availability_topic"] = self._config.mqtt.last_will_topic
        payload["payload_available"] = "alive"
        payload["payload_not_available"] = "dead"
        payload["json_attributes_topic"] = self.state_topic
        payload["json_attributes_template"] = "{{ value_json.attributes | tojson }}"
        payload["device"] = self.device_info
        return json.dumps(payload)

    @staticmethod
    def state_payload(state, attributes=None):
        payload = {}
        payload["state"] = state
        payload["attributes"] = {}
        if attributes:
            payload["attributes"] = attributes
        return json.dumps(payload)

    def on_connect(self, client):
        if self._config.mqtt.home_assistant.enable:
            client.publish(
                self.config_topic, payload=self.config_payload, retain=True,
            )

    def publish(self, state, attributes=None):
        self._mqtt_queue.put(
            {
                "topic": self.state_topic,
                "payload": self.state_payload(state, attributes),
            }
        )
