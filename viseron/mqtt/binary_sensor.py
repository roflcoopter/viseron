"""Home Assistant MQTT binary sensor."""
import json

from viseron.helpers import slugify


class MQTTBinarySensor:
    """Representation of a Home Assistant binary sensor."""

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
        """Return state topic."""
        return (
            f"{self._config.mqtt.client_id}/{self._node_id}/"
            f"binary_sensor/{self.object_id}/state"
        )

    @property
    def config_topic(self):
        """Return config topic."""
        return (
            f"{self._config.mqtt.home_assistant.discovery_prefix}/binary_sensor/"
            f"{self.node_id}/{self.object_id}/config"
        )

    @property
    def name(self):
        """Return name."""
        return self._name

    @property
    def device_name(self):
        """Return device name."""
        return self._device_name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._unique_id

    @property
    def node_id(self):
        """Return node ID."""
        return self._node_id

    @property
    def object_id(self):
        """Return object ID."""
        return self._object_id

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": [self.device_name],
            "name": self.device_name,
            "manufacturer": "Viseron",
        }

    @property
    def config_payload(self):
        """Return config payload."""
        payload = {}
        payload["name"] = self.name  # entitu_id
        payload["unique_id"] = self.unique_id
        payload["state_topic"] = self.state_topic
        payload["value_template"] = "{{ value_json.state | upper }}"
        payload["availability_topic"] = self._config.mqtt.last_will_topic
        payload["payload_available"] = "alive"
        payload["payload_not_available"] = "dead"
        payload["json_attributes_topic"] = self.state_topic
        payload["json_attributes_template"] = "{{ value_json.attributes | tojson }}"
        payload["device"] = self.device_info
        return json.dumps(payload)

    @staticmethod
    def state_payload(state, attributes=None):
        """Return state payload."""
        payload = {}
        payload["state"] = "on" if state else "off"
        payload["attributes"] = {}
        if attributes:
            payload["attributes"] = attributes
        return json.dumps(payload)

    def on_connect(self, client):
        """Called when MQTT connection is established."""
        if self._config.mqtt.home_assistant.enable:
            client.publish(
                self.config_topic,
                payload=self.config_payload,
                retain=True,
            )
        client.publish(self.state_topic, payload=self.state_payload(False))

    def publish(self, state, attributes=None):
        """Publish state."""
        self._mqtt_queue.put(
            {
                "topic": self.state_topic,
                "payload": self.state_payload(state, attributes),
            }
        )
