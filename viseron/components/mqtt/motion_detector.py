"""MQTT-driven external motion detector."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from viseron.domains.motion_detector import (
    CAMERA_SCHEMA_EXTERNAL,
    CONFIG_CAMERAS,
    AbstractMotionDetectorExternal,
)
from viseron.domains.motion_detector.const import DESC_CAMERAS
from viseron.helpers.validators import CameraIdentifier, CoerceNoneToDict

from .const import (
    COMPONENT,
    CONFIG_MOTION_DETECTOR,
    CONFIG_PAYLOAD_OFF,
    CONFIG_PAYLOAD_ON,
    CONFIG_TOPIC,
    DEFAULT_PAYLOAD_OFF,
    DEFAULT_PAYLOAD_ON,
    DESC_PAYLOAD_OFF,
    DESC_PAYLOAD_ON,
    DESC_TOPIC,
)
from .helpers import SubscribeTopic

if TYPE_CHECKING:
    from paho.mqtt.client import MQTTMessage

    from viseron import Viseron


CAMERA_SCHEMA = CAMERA_SCHEMA_EXTERNAL.extend(
    {
        vol.Required(CONFIG_TOPIC, description=DESC_TOPIC): str,
        vol.Optional(
            CONFIG_PAYLOAD_ON,
            default=DEFAULT_PAYLOAD_ON,
            description=DESC_PAYLOAD_ON,
        ): str,
        vol.Optional(
            CONFIG_PAYLOAD_OFF,
            default=DEFAULT_PAYLOAD_OFF,
            description=DESC_PAYLOAD_OFF,
        ): str,
    }
)


MOTION_DETECTOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_CAMERAS, description=DESC_CAMERAS): {
            CameraIdentifier(): vol.All(CoerceNoneToDict(), CAMERA_SCHEMA),
        },
    }
)


def setup(vis: Viseron, config: dict[str, Any], identifier: str) -> bool:
    """Set up the mqtt motion_detector domain."""
    MQTTMotionDetector(vis, config[CONFIG_MOTION_DETECTOR], identifier)
    return True


class MQTTMotionDetector(AbstractMotionDetectorExternal):
    """Motion detector that receives state from an MQTT topic."""

    def __init__(
        self, vis: Viseron, config: dict[str, Any], camera_identifier: str
    ) -> None:
        super().__init__(vis, COMPONENT, config, camera_identifier)
        camera_config = config[CONFIG_CAMERAS][camera_identifier]
        self._topic: str = camera_config[CONFIG_TOPIC]
        self._payload_on: str = camera_config[CONFIG_PAYLOAD_ON]
        self._payload_off: str = camera_config[CONFIG_PAYLOAD_OFF]

        self._mqtt = vis.data[COMPONENT]
        self._motion_topic = SubscribeTopic(
            topic=self._topic, callback=self._on_message
        )
        self._mqtt.subscribe(self._motion_topic)
        self._logger.debug("Subscribed to MQTT topic %s", self._topic)

    def _parse_payload(self, payload: str) -> bool | None:
        """Return ``True``/``False`` motion state, or ``None`` if unknown."""
        try:
            data = json.loads(payload)
        except (ValueError, TypeError):
            data = None

        if isinstance(data, dict) and isinstance(data.get("detected"), bool):
            return data["detected"]

        if payload == self._payload_on:
            return True
        if payload == self._payload_off:
            return False
        return None

    def _on_message(self, msg: MQTTMessage) -> None:
        """Handle an incoming MQTT message."""
        try:
            payload = msg.payload.decode()
        except (AttributeError, UnicodeDecodeError):
            self._logger.debug("Ignoring undecodable payload on %s", self._topic)
            return

        state = self._parse_payload(payload)
        if state is None:
            self._logger.debug(
                "Ignoring unrecognised payload %r on %s", payload, self._topic
            )
            return

        self.set_motion_detected(state)

    def unload(self) -> None:
        """Unload the motion detector."""
        self._mqtt.unsubscribe(self._motion_topic)
        super().unload()
        self._logger.debug("Unsubscribed from MQTT topic %s", self._topic)
