import json


class MQTTBinarySensor:
    def __init__(self, config, mqtt_queue, name=None):
        self.config = config
        self.mqtt_queue = mqtt_queue
        self.name = f"{self.config.camera.mqtt_name} {name}" if name else name

    @property
    def base_topic(self):
        return (
            f"{self.config.mqtt.discovery_prefix}/binary_sensor/"
            f"{self.config.camera.mqtt_name}"
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
        payload["name"] = self.name if self.name else self.config.camera.mqtt_name
        payload["state_topic"] = self.state_topic
        payload["value_template"] = "{{ value_json.state }}"
        payload["availability_topic"] = self.config.mqtt.last_will_topic
        payload["payload_available"] = "alive"
        payload["payload_not_available"] = "dead"
        payload["json_attributes_topic"] = self.state_topic
        return json.dumps(payload, indent=3)

    def on_connect(self, client):
        client.publish(
            self.config_topic, payload=self.config_payload, retain=True,
        )
        client.publish(self.state_topic, payload=json.dumps({"state": "off"}))

    def publish(self, value):
        payload = {}
        payload["state"] = "on" if value else "off"
        self.mqtt_queue.put(
            {"topic": self.state_topic, "payload": json.dumps(payload, indent=3)}
        )
