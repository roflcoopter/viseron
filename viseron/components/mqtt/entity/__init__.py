"""MQTT entity."""
from __future__ import annotations

import json
from functools import partial
from typing import TYPE_CHECKING, Generic, TypeVar

from viseron.components.mqtt.const import COMPONENT as MQTT_COMPONENT
from viseron.components.mqtt.helpers import PublishPayload
from viseron.helpers.entity import Entity
from viseron.helpers.json import JSONEncoder

if TYPE_CHECKING:
    from viseron import Viseron

T = TypeVar("T", bound=Entity)


class MQTTEntity(Generic[T]):
    """Class that relays Entity state and attributes to the MQTT broker."""

    def __init__(self, vis: Viseron, config, entity: T) -> None:
        self._vis = vis
        self._config = config
        self.entity = entity

        self._mqtt = vis.data[MQTT_COMPONENT]

    @property
    def state_topic(self) -> str:
        """Return state topic."""
        return (
            f"{self._mqtt.base_topic}/{self.entity.domain}/"
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
