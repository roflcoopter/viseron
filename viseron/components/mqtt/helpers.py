"""MQTT helpers."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class PublishPayload:
    """Payload to publish to MQTT."""

    topic: str
    payload: Any
    retain: bool = False


@dataclass
class SubscribeTopic:
    """Subscribe to a topic."""

    topic: str
    callback: Callable
