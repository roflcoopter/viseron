"""MQTT entity."""
from __future__ import annotations

import json
from functools import partial
from typing import TYPE_CHECKING

from viseron.components.mqtt.const import COMPONENT as MQTT_COMPONENT, CONFIG_CLIENT_ID
from viseron.components.mqtt.helpers import PublishPayload
from viseron.helpers.json import JSONEncoder

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.mqtt import MQTT
    from viseron.helpers.entity import Entity


class MQTTEntity:
    """Class that relays Entity state and attributes to the MQTT broker."""

    def __init__(self, vis: Viseron, config, entity: Entity) -> None:
        self._vis = vis
        self._config = config
        self.entity = entity

        self._mqtt: MQTT = vis.data[MQTT_COMPONENT]

    @property
    def state_topic(self):
        """Return state topic."""
        return (
            f"{self._config[CONFIG_CLIENT_ID]}/{self.entity.domain}/"
            f"{self.entity.object_id}/state"
        )

    @property
    def attributes_topic(self):
        """Return attributes topic."""
        return self.state_topic

    def publish_state(self) -> None:
        """Publish state to MQTT."""
        payload = {}
        payload["state"] = self.entity.state
        payload["attributes"] = self.entity.attributes
        self._mqtt.publish(
            PublishPayload(
                self.state_topic,
                partial(json.dumps, cls=JSONEncoder, allow_nan=False)(payload),
                retain=True,
            )
        )
