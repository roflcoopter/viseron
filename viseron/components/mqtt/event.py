"""MQTT event dataclasses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .entity import MQTTEntity


@dataclass
class EventMQTTEntityAddedData:
    """MQTT entity added event data."""

    mqtt_entity: MQTTEntity
