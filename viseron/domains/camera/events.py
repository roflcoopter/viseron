"""Events for the camera domain."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from viseron.events import EventData
from viseron.types import SupportedDomains


@dataclass
class EventCameraEventData(EventData):
    """Dataclass for camera events."""

    camera_identifier: str
    domain: SupportedDomains
    operation: Literal["insert", "update", "delete"]
    data: Any
