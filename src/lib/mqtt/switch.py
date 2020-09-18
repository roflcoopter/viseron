import json

import logging

LOGGER = logging.getLogger(__name__)


class MQTTSwitch:
    def __init__(self, config, mqtt_queue):
        self._config = config
        self._mqtt_queue = mqtt_queue

    @property
    def base_topic(self):
        return (
            f"{self._config.mqtt.discovery_prefix}/switch/"
            f"{self._config.camera.mqtt_name}"
        )

    @property
    def state_topic(self):
        return f"{self.base_topic}/state"

    @property
    def config_topic(self):
        return f"{self.base_topic}/config"

    @property
    def command_topic(self):
        return (
            f"{self._config.mqtt.discovery_prefix}/switch/"
            f"{self._config.camera.mqtt_name}/set"
        )

    @property
    def config_payload(self):
        payload = {}
        payload["name"] = self._config.camera.mqtt_name
        payload["command_topic"] = self.command_topic
        payload["state_topic"] = self.state_topic
        payload["retain"] = True
        payload["availability_topic"] = self._config.mqtt.last_will_topic
        payload["payload_available"] = "alive"
        payload["payload_not_available"] = "dead"
        return json.dumps(payload, indent=3)

    def on_connect(self, client):
        client.publish(
            self.config_topic, payload=self.config_payload, retain=True,
        )
        client.publish(self.state_topic, payload="off")

    def on_message(self, message):
        self._mqtt_queue.put(
            {"topic": self.state_topic, "payload": str(message.payload.decode()),}
        )
