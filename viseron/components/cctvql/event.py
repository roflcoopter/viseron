"""Events for the cctvQL component."""

from __future__ import annotations

from dataclasses import dataclass

from viseron.events import EventData


@dataclass
class EventCctvqlEnrichmentData(EventData):
    """Data carried by EVENT_CCTVQL_ENRICHMENT."""

    camera_name: str
    query: str
    answer: str
    intent: str
    labels: list[str]
