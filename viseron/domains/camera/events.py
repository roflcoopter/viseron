"""Events for the camera domain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from viseron.events import EventData

if TYPE_CHECKING:
    from viseron.viseron_types import SupportedDomains


@dataclass
class EventCameraEventData(EventData):
    """Dataclass for camera events."""

    camera_identifier: str
    domain: SupportedDomains
    operation: Literal["insert", "update", "delete"]
    data: Any
