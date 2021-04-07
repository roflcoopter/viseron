import json

import logging

LOGGER = logging.getLogger(__name__)


class MQTTSwitch:
    def __init__(self, config, mqtt_queue):
        self._config = config
        self._mqtt_queue = mqtt_queue
        self._name = config.camera.mqtt_name
        self._device_name = f"{config.mqtt.client_id} {config.camera.name}"
        self._unique_id = self.name

    @property
    def state_topic(self):
        return f"{self._config.mqtt.client_id}/{self.name}/switch/state"

    @property
    def config_topic(self):
        return (
            f"{self._config.mqtt.home_assistant.discovery_prefix}/switch/"
            f"{self.name}/config"
        )

    @property
    def command_topic(self):
        return f"{self._config.mqtt.client_id}/{self.name}/switch/set"

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
        payload["name"] = self._config.camera.mqtt_name
        payload["unique_id"] = self.unique_id
        payload["command_topic"] = self.command_topic
        payload["state_topic"] = self.state_topic
        payload["value_template"] = "{{ value_json.state | upper }}"
        payload["retain"] = True
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

    def on_message(self, message):
        self._mqtt_queue.put(
            {
                "topic": self.state_topic,
                "payload": self.state_payload(str(message.payload.decode())),
            }
        )
