"""MQTT event dataclasses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from viseron.events import EventData

if TYPE_CHECKING:
    from .entity import MQTTEntity


@dataclass
class EventMQTTEntityAddedData(EventData):
    """MQTT entity added event data."""

    mqtt_entity: MQTTEntity
