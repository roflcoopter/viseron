"""This module contains classes related to events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic

from typing_extensions import TypeVar

T = TypeVar("T")


@dataclass
class Event(Generic[T]):
    """Dataclass that holds an event."""

    name: str
    data: T
    timestamp: float

    def as_dict(self) -> dict[str, Any]:
        """Convert Event to dict."""
        return {
            "name": self.name,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class EventData:
    """Base class that holds event data."""

    # Indicates if the event is a JSON serializable object
    json_serializable: bool = True


class EventEmptyData(EventData):
    """Empty event data."""

    def as_dict(self) -> dict[str, Any]:
        """Convert EventEmptyData to dict."""
        return {}
