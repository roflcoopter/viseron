"""mqtt component constants."""
from typing import Final

COMPONENT = "mqtt"
DESC_COMPONENT = "MQTT configuration."

MQTT_RC = {
    0: "Connection successful",
    1: "Connection refused - incorrect protocol version",
    2: "Connection refused - invalid client identifier",
    3: "Connection refused - server unavailable",
    4: "Connection refused - bad username or password",
    5: "Connection refused - not authorised",
}

MQTT_MANUAL_RECORDING_COMMAND_TOPIC = (
    "{client_id}/{camera_identifier}/manual_recording/command"
)

MQTT_CLIENT_CONNECTION_TOPIC = "{client_id}/state"
MQTT_CLIENT_CONNECTION_ONLINE = "online"
MQTT_CLIENT_CONNECTION_OFFLINE = "offline"


# Event topic constants
EVENT_MQTT_ENTITY_ADDED = "mqtt/entity_added"


# HOME_ASSISTANT_SCHEMA constants
CONFIG_DISCOVERY_PREFIX = "discovery_prefix"
CONFIG_RETAIN_CONFIG = "retain_config"

DEFAULT_DISCOVERY_PREFIX = "homeassistant"
DEFAULT_RETAIN_CONFIG = True

DESC_DISCOVERY_PREFIX = (
    "<a href=https://www.home-assistant.io/docs/mqtt/discovery/#discovery_prefix>"
    "Discovery prefix.</a>"
)
DESC_RETAIN_CONFIG = "Retain config topic messages."


# CONFIG_SCHEMA constants
CONFIG_BROKER = "broker"
CONFIG_PORT = "port"
CONFIG_USERNAME = "username"
CONFIG_PASSWORD = "password"
CONFIG_CLIENT_ID = "client_id"
CONFIG_HOME_ASSISTANT = "home_assistant"
CONFIG_LAST_WILL_TOPIC = "last_will_topic"

DEFAULT_PORT = 1883
DEFAULT_USERNAME: Final = None
DEFAULT_PASSWORD: Final = None
DEFAULT_CLIENT_ID = "viseron"
DEFAULT_LAST_WILL_TOPIC: Final = None

DESC_BROKER = "IP address or hostname of MQTT broker."
DESC_PORT = "Port the broker is listening on."
DESC_USERNAME = "Username for the broker."
DESC_PASSWORD = "Password for the broker."
DESC_CLIENT_ID = (
    "Client ID used when connecting to broker.</br>"
    "Also used as the base for all topics."
)
DESC_HOME_ASSISTANT = (
    "See <a href=#home-assistant-mqtt-discovery>Home Assistant MQTT Discovery.</a>"
)
DESC_LAST_WILL_TOPIC = "Last will topic."

INCLUSION_GROUP_AUTHENTICATION = "authentication"

MESSAGE_AUTHENTICATION = "username and password must be provided together"
