"""MQTT config."""

from voluptuous import All, Any, Optional, Required, Schema


def get_lwt_topic(mqtt: dict) -> dict:
    """Return last will topic."""
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
    """Home Assistant integration config."""

    def __init__(self, home_assistant):
        self._enable = home_assistant["enable"]
        self._discovery_prefix = home_assistant["discovery_prefix"]

    @property
    def enable(self):
        """Return if integration is enabled."""
        return self._enable

    @property
    def discovery_prefix(self):
        """Return Home Assistant discovery prefix."""
        return self._discovery_prefix


class MQTTConfig:
    """MQTT config."""

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
        """Return broker IP or hostname."""
        return self._broker

    @property
    def port(self):
        """Return broker port."""
        return self._port

    @property
    def username(self):
        """Return broker username."""
        return self._username

    @property
    def password(self):
        """Return broker password."""
        return self._password

    @property
    def client_id(self):
        """Return client id."""
        return self._client_id

    @property
    def home_assistant(self):
        """Return Home Assistant integration config."""
        return self._home_assistant

    @property
    def last_will_topic(self):
        """Return last will topic."""
        return self._last_will_topic
