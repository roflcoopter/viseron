import json
from lib.helpers import slugify


class MQTTBinarySensor:
    def __init__(self, config, mqtt_queue, name):
        self._config = config
        self._mqtt_queue = mqtt_queue
        self._name = (
            f"{config.camera.mqtt_name} {name}" if name else config.camera.mqtt_name
        )
        self._object_id = slugify(name)

    @property
    def base_topic(self):
        if self._object_id:
            return (
                f"{self._config.mqtt.discovery_prefix}/binary_sensor/"
                f"{self._config.camera.mqtt_name}/{self._object_id}"
            )
        return (
            f"{self._config.mqtt.discovery_prefix}/binary_sensor/"
            f"{self._config.camera.mqtt_name}"
        )

    @property
    def state_topic(self):
        return f"{self.base_topic}/state"

    @property
    def config_topic(self):
        return f"{self.base_topic}/config"

    @property
    def config_payload(self):
        payload = {}
        payload["name"] = self._name
        payload["state_topic"] = self.state_topic
        payload["value_template"] = "{{ value | upper }}"
        payload["availability_topic"] = self._config.mqtt.last_will_topic
        payload["payload_available"] = "alive"
        payload["payload_not_available"] = "dead"
        payload["json_attributes_topic"] = self.state_topic
        return json.dumps(payload, indent=3)

    def on_connect(self, client):
        client.publish(
            self.config_topic, payload=self.config_payload, retain=True,
        )
        client.publish(self.state_topic, payload="off")

    def publish(self, value):
        self._mqtt_queue.put(
            {"topic": self.state_topic, "payload": ("on" if value else "off")}
        )
