import logging

from voluptuous import (
    All,
    Any,
    Required,
    Schema,
    Optional,
)

LOGGER = logging.getLogger(__name__)


def get_lwt_topic(mqtt: dict) -> dict:
    if not mqtt["last_will_topic"]:
        mqtt["last_will_topic"] = f"{mqtt['client_id']}/lwt"
    return mqtt


SCHEMA = Schema(
    All(
        {
            Required("broker"): str,
            Optional("port", default=1883): int,
            Optional("username", default=None): Any(str, None),
            Optional("password", default=None): Any(str, None),
            Optional("client_id", default="viseron"): Any(str, None),
            Optional("home_assistant", default={}): {
                Optional("enable", default=True): bool,
                Optional("discovery_prefix", default="homeassistant"): str,
            },
            Optional("last_will_topic", default=None): Any(str, None),
        },
        get_lwt_topic,
    )
)


class HomeAssistant:
    def __init__(self, home_assistant):
        self._enable = home_assistant["enable"]
        self._discovery_prefix = home_assistant["discovery_prefix"]

    @property
    def enable(self):
        return self._enable

    @property
    def discovery_prefix(self):
        return self._discovery_prefix


class MQTTConfig:
    schema = SCHEMA

    def __init__(self, mqtt):
        self._broker = mqtt["broker"]
        self._port = mqtt["port"]
        self._username = mqtt["username"]
        self._password = mqtt["password"]
        self._client_id = mqtt["client_id"]
        self._home_assistant = HomeAssistant(mqtt["home_assistant"])
        self._last_will_topic = mqtt["last_will_topic"]

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
    def home_assistant(self):
        return self._home_assistant

    @property
    def last_will_topic(self):
        return self._last_will_topic
