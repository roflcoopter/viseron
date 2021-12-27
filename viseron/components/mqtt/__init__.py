"""MQTT interface."""
import json
import logging
from queue import Empty, Queue
from typing import Callable, Dict, List

import paho.mqtt.client as mqtt
import voluptuous as vol

from viseron import EventData, Viseron
from viseron.const import EVENT_STATE_CHANGED, VISERON_SIGNAL_SHUTDOWN
from viseron.helpers.validators import none_to_dict
from viseron.watchdog.thread_watchdog import RestartableThread

from .const import (
    COMPONENT,
    CONFIG_BROKER,
    CONFIG_CLIENT_ID,
    CONFIG_DISCOVERY_PREFIX,
    CONFIG_HOME_ASSISTANT,
    CONFIG_LAST_WILL_TOPIC,
    CONFIG_PASSWORD,
    CONFIG_PORT,
    CONFIG_RETAIN_CONFIG,
    CONFIG_USERNAME,
    DEFAULT_CLIENT_ID,
    DEFAULT_DISCOVERY_PREFIX,
    DEFAULT_LAST_WILL_TOPIC,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_RETAIN_CONFIG,
    DEFAULT_USERNAME,
    INCLUSION_GROUP_AUTHENTICATION,
    MESSAGE_AUTHENTICATION,
    MQTT_CLIENT_CONNECTION_OFFLINE,
    MQTT_CLIENT_CONNECTION_ONLINE,
    MQTT_CLIENT_CONNECTION_TOPIC,
    MQTT_RC,
)
from .helpers import PublishPayload, SubscribeTopic
from .homeassistant import HassMQTTInterface

LOGGER = logging.getLogger(__name__)


def get_lwt_topic(mqtt_config: dict) -> dict:
    """Return last will topic."""
    if not mqtt_config["last_will_topic"]:
        mqtt_config["last_will_topic"] = f"{mqtt_config['client_id']}/lwt"
    return mqtt_config


HOME_ASSISTANT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONFIG_DISCOVERY_PREFIX, default=DEFAULT_DISCOVERY_PREFIX): str,
        vol.Optional(CONFIG_RETAIN_CONFIG, default=DEFAULT_RETAIN_CONFIG): bool,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT: vol.Schema(
            vol.All(
                {
                    vol.Required(CONFIG_BROKER): str,
                    vol.Optional(CONFIG_PORT, default=DEFAULT_PORT): int,
                    vol.Inclusive(
                        CONFIG_USERNAME,
                        INCLUSION_GROUP_AUTHENTICATION,
                        default=DEFAULT_USERNAME,
                        msg=MESSAGE_AUTHENTICATION,
                    ): vol.Maybe(str),
                    vol.Inclusive(
                        CONFIG_PASSWORD,
                        INCLUSION_GROUP_AUTHENTICATION,
                        default=DEFAULT_PASSWORD,
                        msg=MESSAGE_AUTHENTICATION,
                    ): vol.Maybe(str),
                    vol.Optional(
                        CONFIG_CLIENT_ID, default=DEFAULT_CLIENT_ID
                    ): vol.Maybe(str),
                    vol.Optional(CONFIG_HOME_ASSISTANT): vol.All(
                        none_to_dict, HOME_ASSISTANT_SCHEMA
                    ),
                    vol.Optional(
                        CONFIG_LAST_WILL_TOPIC, default=DEFAULT_LAST_WILL_TOPIC
                    ): vol.Maybe(str),
                },
                get_lwt_topic,
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config):
    """Set up the mqtt component."""
    config = config[COMPONENT]
    mqtt_client = MQTT(vis, config)
    mqtt_client.connect()
    vis.data[COMPONENT] = mqtt_client
    vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, mqtt_client.stop)

    if config.get(CONFIG_HOME_ASSISTANT, None):
        HassMQTTInterface(vis, config)

    return True


class MQTT:
    """MQTT interface."""

    def __init__(self, vis, config):
        self._vis = vis
        self._config = config

        self._client: mqtt.Client = None
        self._publish_queue: Queue = Queue(maxsize=1000)
        self._subscriptions: Dict[str, List[Callable]] = {}

        self._kill_received = False
        vis.listen_event(EVENT_STATE_CHANGED, self.state_changed)

    def on_connect(self, _client, _userdata, _flags, returncode):
        """On established MQTT connection."""
        LOGGER.debug(f"MQTT connected with returncode {str(returncode)}")
        if returncode != 0:
            LOGGER.error(
                f"Could not connect to broker. Returncode: {returncode}: "
                f"{MQTT_RC.get(returncode, 'Unknown error')}"
            )

        # Send initial alive message
        self.publish(
            PublishPayload(
                topic=self._config[CONFIG_LAST_WILL_TOPIC], payload="alive", retain=True
            )
        )
        self.publish(
            PublishPayload(
                topic=MQTT_CLIENT_CONNECTION_TOPIC.format(
                    client_id=self._config[CONFIG_CLIENT_ID]
                ),
                payload=MQTT_CLIENT_CONNECTION_ONLINE,
                retain=True,
            )
        )

    def on_message(self, _client, _userdata, msg):
        """On message received."""
        LOGGER.debug(f"Got topic {msg.topic}, message {str(msg.payload.decode())}")
        for callback in self._subscriptions[msg.topic]:
            callback(msg)

    def connect(self):
        """Connect to broker."""
        self._client = mqtt.Client(self._config[CONFIG_CLIENT_ID])
        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message
        self._client.enable_logger(logger=logging.getLogger(f"{__name__}.client"))
        logging.getLogger(f"{__name__}.client").setLevel(logging.INFO)
        if self._config[CONFIG_USERNAME]:
            self._client.username_pw_set(
                self._config[CONFIG_USERNAME], self._config[CONFIG_PASSWORD]
            )

        RestartableThread(
            name=f"{__name__}.publisher",
            target=self.publisher,
            daemon=True,
            register=True,
        ).start()

        # Set a Last Will message
        self._client.will_set(
            self._config[CONFIG_LAST_WILL_TOPIC], payload="dead", retain=True
        )
        self._client.connect(self._config[CONFIG_BROKER], self._config[CONFIG_PORT], 10)

        # Start threaded loop to read/publish messages
        self._client.loop_start()

    def subscribe(self, subscription: SubscribeTopic):
        """Subscribe to a topic."""
        if subscription.topic not in self._subscriptions:
            self._client.subscribe(subscription.topic)

        self._subscriptions.setdefault(subscription.topic, [])
        self._subscriptions[subscription.topic].append(subscription.callback)

    def publish(self, payload: PublishPayload):
        """Put payload in publish queue."""
        self._publish_queue.put(payload)

    def publisher(self):
        """Publish thread."""
        while not self._kill_received:
            try:
                message: PublishPayload = self._publish_queue.get(timeout=1)
            except Empty:
                continue

            self._client.publish(
                message.topic,
                payload=message.payload,
                retain=message.retain,
            )

    def state_changed(self, event_data: EventData):
        """Relay entity state change to MQTT."""
        entity = event_data.data.entity

        payload = {}
        payload["state"] = entity.state
        payload["attributes"] = entity.attributes
        self.publish(
            PublishPayload(
                f"{self._config[CONFIG_CLIENT_ID]}/{entity.domain}/"
                f"{entity.object_id}/state",
                json.dumps(payload),
                retain=True,
            )
        )

    def stop(self):
        """Stop mqtt client."""
        LOGGER.debug("Stopping MQTT client")
        # Publish using client directly so we are sure its published
        self._client.publish(
            topic=MQTT_CLIENT_CONNECTION_TOPIC.format(
                client_id=self._config[CONFIG_CLIENT_ID]
            ),
            payload=MQTT_CLIENT_CONNECTION_OFFLINE,
            retain=True,
        )
        self._kill_received = True
        self._client.disconnect()
        self._client.loop_stop()
