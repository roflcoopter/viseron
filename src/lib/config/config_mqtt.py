import logging

from voluptuous import (
    Any,
    Required,
    Schema,
    Optional,
)

LOGGER = logging.getLogger(__name__)

SCHEMA = Schema(
    {
        Required("broker"): str,
        Required("port", default=1883): int,
        Optional("username", default=None): Any(str, None),
        Optional("password", default=None): Any(str, None),
        Optional("client_id", default="viseron"): Any(str, None),
        Optional("discovery_prefix", default="homeassistant"): str,
        Optional("last_will_topic", default="viseron/lwt"): str,
    }
)


class MQTTConfig:
    schema = SCHEMA

    def __init__(self, mqtt):
        self._broker = mqtt.broker
        self._port = mqtt.port
        self._username = mqtt.username
        self._password = mqtt.password
        self._client_id = mqtt.client_id
        self._discovery_prefix = mqtt.discovery_prefix
        self._last_will_topic = mqtt.last_will_topic

    @property
    def broker(self):
        return self._broker

    @property
    def port(self):
        return self._port

    @property
    def username(self):
        return self._username

    @property
    def password(self):
        return self._password

    @property
    def client_id(self):
        return self._client_id

    @property
    def discovery_prefix(self):
        return self._discovery_prefix

    @property
    def last_will_topic(self):
        return self._last_will_topic
