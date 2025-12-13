"""MQTT interface."""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

import paho.mqtt.client as mqtt
import voluptuous as vol

from viseron.components.nvr.toggle import ManualRecordingToggle
from viseron.const import (
    EVENT_ENTITY_ADDED,
    EVENT_STATE_CHANGED,
    VISERON_SIGNAL_SHUTDOWN,
)
from viseron.helpers.validators import CoerceNoneToDict, Maybe
from viseron.states import EventEntityAddedData
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
    DESC_BROKER,
    DESC_CLIENT_ID,
    DESC_COMPONENT,
    DESC_DISCOVERY_PREFIX,
    DESC_HOME_ASSISTANT,
    DESC_LAST_WILL_TOPIC,
    DESC_PASSWORD,
    DESC_PORT,
    DESC_RETAIN_CONFIG,
    DESC_USERNAME,
    EVENT_MQTT_ENTITY_ADDED,
    INCLUSION_GROUP_AUTHENTICATION,
    MESSAGE_AUTHENTICATION,
    MQTT_CLIENT_CONNECTION_OFFLINE,
    MQTT_CLIENT_CONNECTION_ONLINE,
    MQTT_CLIENT_CONNECTION_TOPIC,
    MQTT_RC,
)
from .entity import MQTTEntity
from .entity.binary_sensor import BinarySensorMQTTEntity
from .entity.image import ImageMQTTEntity
from .entity.sensor import SensorMQTTEntity
from .entity.toggle import ManualRecordingToggleMQTTEntity, ToggleMQTTEntity
from .event import EventMQTTEntityAddedData
from .helpers import PublishPayload, SubscribeTopic
from .homeassistant import HassMQTTInterface

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.helpers.entity import Entity

LOGGER = logging.getLogger(__name__)


def get_lwt_topic(mqtt_config: dict) -> dict:
    """Return last will topic."""
    if not mqtt_config["last_will_topic"]:
        mqtt_config["last_will_topic"] = f"{mqtt_config['client_id']}/lwt"
    return mqtt_config


HOME_ASSISTANT_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONFIG_DISCOVERY_PREFIX,
            default=DEFAULT_DISCOVERY_PREFIX,
            description=DESC_DISCOVERY_PREFIX,
        ): str,
        vol.Optional(
            CONFIG_RETAIN_CONFIG,
            default=DEFAULT_RETAIN_CONFIG,
            description=DESC_RETAIN_CONFIG,
        ): bool,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): vol.Schema(
            vol.All(
                {
                    vol.Required(CONFIG_BROKER, description=DESC_BROKER): str,
                    vol.Optional(
                        CONFIG_PORT, default=DEFAULT_PORT, description=DESC_PORT
                    ): int,
                    vol.Inclusive(
                        CONFIG_USERNAME,
                        INCLUSION_GROUP_AUTHENTICATION,
                        default=DEFAULT_USERNAME,
                        description=DESC_USERNAME,
                        msg=MESSAGE_AUTHENTICATION,
                    ): Maybe(str),
                    vol.Inclusive(
                        CONFIG_PASSWORD,
                        INCLUSION_GROUP_AUTHENTICATION,
                        default=DEFAULT_PASSWORD,
                        description=DESC_PASSWORD,
                        msg=MESSAGE_AUTHENTICATION,
                    ): Maybe(str),
                    vol.Optional(
                        CONFIG_CLIENT_ID,
                        default=DEFAULT_CLIENT_ID,
                        description=DESC_CLIENT_ID,
                    ): Maybe(str),
                    vol.Optional(
                        CONFIG_LAST_WILL_TOPIC,
                        default=DEFAULT_LAST_WILL_TOPIC,
                        description=DESC_LAST_WILL_TOPIC,
                    ): Maybe(str),
                    vol.Optional(
                        CONFIG_HOME_ASSISTANT,
                        description=DESC_HOME_ASSISTANT,
                    ): vol.All(CoerceNoneToDict(), HOME_ASSISTANT_SCHEMA),
                },
                get_lwt_topic,
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)


ENTITY_MAP: dict[str, type[MQTTEntity]] = {
    "binary_sensor": BinarySensorMQTTEntity,
    "image": ImageMQTTEntity,
    "sensor": SensorMQTTEntity,
    "toggle": ToggleMQTTEntity,
}

ENTITY_OVERRIDES: dict[type, type[MQTTEntity]] = {
    ManualRecordingToggle: ManualRecordingToggleMQTTEntity,
}


def setup(vis: Viseron, config) -> bool:
    """Set up the mqtt component."""
    config = config[COMPONENT]
    mqtt_client = MQTT(vis, config)
    mqtt_client.connect()
    vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, mqtt_client.stop)

    if config.get(CONFIG_HOME_ASSISTANT, None):
        HassMQTTInterface(vis, config)

    return True


class MQTT:
    """MQTT interface."""

    def __init__(self, vis: Viseron, config: dict[str, Any]) -> None:
        self._vis = vis
        self._config = config

        self._client = mqtt.Client(client_id=self._config[CONFIG_CLIENT_ID])
        self._publish_queue: Queue = Queue(maxsize=1000)
        self._subscriptions: dict[str, list[Callable]] = {}

        self._connected = False
        self._reconnect = False
        self._kill_received = False

        vis.data[COMPONENT] = self

        self._entity_creation_lock = threading.Lock()
        self._entities: dict[str, MQTTEntity] = {}

    def create_entity(self, entity: Entity) -> None:
        """Create entity in Home Assistant."""
        with self._entity_creation_lock:
            if entity.entity_id in self._entities:
                LOGGER.debug(f"Entity {entity.entity_id} has already been added")
                return

            if entity_class := ENTITY_OVERRIDES.get(type(entity)):
                mqtt_entity = entity_class(self._vis, self._config, entity)
            elif entity_class := ENTITY_MAP.get(entity.domain):
                mqtt_entity = entity_class(self._vis, self._config, entity)
            else:
                LOGGER.debug(f"Unsupported domain encountered: {entity.domain}")
                return

            self._entities[entity.entity_id] = mqtt_entity
            self._vis.dispatch_event(
                EVENT_MQTT_ENTITY_ADDED,
                EventMQTTEntityAddedData(mqtt_entity),
                store=False,
            )

    def create_entities(self, entities: dict[str, Entity]) -> None:
        """Create entities in Home Assistant."""
        for entity in entities.values():
            self.create_entity(entity)

    def entity_added(self, event_data: Event) -> None:
        """Add entity to Home Assistant when its added to Viseron."""
        entity_added_data: EventEntityAddedData = event_data.data
        self.create_entity(entity_added_data.entity)

    def get_entities(self):
        """Return registered MQTT entities."""
        return self._entities

    def on_connect(self, _client, _userdata, _flags, returncode) -> None:
        """On established MQTT connection."""
        LOGGER.debug(f"MQTT connected with returncode {str(returncode)}")
        if returncode != 0:
            LOGGER.error(
                f"Could not connect to broker. Returncode: {returncode}: "
                f"{MQTT_RC.get(returncode, 'Unknown error')}"
            )
            return
        self._connected = True

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

        if self._reconnect:
            LOGGER.debug("Reconnected to MQTT broker, re-subscribing to topics")
            self._reconnect = False
            # Re-subscribe to all topics
            for topic, _ in self._subscriptions.items():
                LOGGER.debug(f"Re-subscribing to topic {topic}")
                self._client.subscribe(topic)
            return

        self._vis.listen_event(EVENT_ENTITY_ADDED, self.entity_added)
        self.create_entities(self._vis.get_entities())
        self._vis.listen_event(EVENT_STATE_CHANGED, self.state_changed)

    def on_disconnect(self, _client, _userdata, returncode) -> None:
        """On MQTT disconnection."""
        LOGGER.warning(f"MQTT disconnected with returncode {str(returncode)}")
        if self._connected:
            self._reconnect = True
            self._connected = False

    def on_message(self, _client, _userdata, msg) -> None:
        """On message received."""
        LOGGER.debug(
            f"Message received on topic {msg.topic}, "
            f"message {str(msg.payload.decode())}"
        )
        for callback in self._subscriptions[msg.topic]:
            # Run callback in thread to not block the message queue
            RestartableThread(
                name=f"mqtt_callback.{callback}",
                target=callback,
                args=(msg,),
                daemon=True,
                register=False,
            ).start()

    def connect(self) -> None:
        """Connect to broker."""
        self._client.on_connect = self.on_connect
        self._client.on_disconnect = self.on_disconnect
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

    def subscribe(self, subscription: SubscribeTopic) -> None:
        """Subscribe to a topic."""
        if subscription.topic not in self._subscriptions:
            self._client.subscribe(subscription.topic)

        LOGGER.debug(f"Subscribing to topic {subscription.topic}")
        self._subscriptions.setdefault(subscription.topic, [])
        self._subscriptions[subscription.topic].append(subscription.callback)

    def publish(self, payload: PublishPayload) -> None:
        """Put payload in publish queue."""
        self._publish_queue.put(payload)

    def publisher(self) -> None:
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

    def state_changed(self, event_data: Event) -> None:
        """Relay entity state change to MQTT."""
        with self._entity_creation_lock:
            entity_id = event_data.data.entity_id

            if entity_id not in self._entities:
                LOGGER.error(f"State change triggered for missing entity {entity_id}")
                return

            self._entities[entity_id].publish_state()

    def stop(self) -> None:
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
