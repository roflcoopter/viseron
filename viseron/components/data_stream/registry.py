"""Subscriber storage and topic matching for the data_stream component."""

from __future__ import annotations

import fnmatch
import logging
import re
import threading
from typing import TYPE_CHECKING

from viseron.components.data_stream.const import MATCH_CACHE_MAXSIZE

if TYPE_CHECKING:
    import uuid

    from viseron.components.data_stream.subscriber import Subscriber

LOGGER = logging.getLogger(__name__)


class SubscriberRegistry:
    """Hold subscribers and resolve which ones a topic reaches.

    Subscriber lists are stored as immutable tuples that are rebuilt on
    subscribe/unsubscribe, so the publish path can iterate them without copying
    or locking. Wildcard patterns are compiled once and the topics they match
    are memoized, turning wildcard dispatch into a single dict lookup.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._static: dict[str, tuple[Subscriber, ...]] = {}
        self._wildcard: dict[str, tuple[Subscriber, ...]] = {}
        self._patterns: dict[str, re.Pattern[str]] = {}
        self._match_cache: dict[str, tuple[Subscriber, ...]] = {}

    @property
    def topic_count(self) -> int:
        """Return the number of topics that still have a subscriber."""
        return len(self._static) + len(self._wildcard)

    def add(self, subscriber: Subscriber) -> None:
        """Register a subscriber."""
        data_topic = subscriber.data_topic
        with self._lock:
            if "*" in data_topic:
                self._wildcard[data_topic] = (
                    *self._wildcard.get(data_topic, ()),
                    subscriber,
                )
                if data_topic not in self._patterns:
                    self._patterns[data_topic] = re.compile(
                        fnmatch.translate(data_topic)
                    )
                self._match_cache.clear()
                return

            self._static[data_topic] = (*self._static.get(data_topic, ()), subscriber)

    def remove(self, data_topic: str, unique_id: uuid.UUID) -> None:
        """Unregister a subscriber.

        Unknown topics and ids are ignored. Every unsub() closure handed out by
        Viseron.listen_event runs during teardown, which is after shutdown has
        already called clear().
        """
        with self._lock:
            store = self._wildcard if "*" in data_topic else self._static
            existing = store.get(data_topic)
            if existing is None:
                LOGGER.debug(f"No subscribers left on data topic {data_topic}")
                return

            remaining = tuple(
                subscriber
                for subscriber in existing
                if subscriber.unique_id != unique_id
            )
            if remaining:
                store[data_topic] = remaining
            else:
                del store[data_topic]
                self._patterns.pop(data_topic, None)

            if store is self._wildcard:
                self._match_cache.clear()

    def clear(self) -> None:
        """Remove every subscriber."""
        with self._lock:
            self._static.clear()
            self._wildcard.clear()
            self._patterns.clear()
            self._match_cache.clear()

    def static_subscribers(self, data_topic: str) -> tuple[Subscriber, ...]:
        """Return subscribers registered on an exact topic."""
        return self._static.get(data_topic, ())

    def wildcard_subscribers(self, data_topic: str) -> tuple[Subscriber, ...]:
        """Return subscribers whose pattern matches a topic."""
        if not self._wildcard:
            return ()

        cached = self._match_cache.get(data_topic)
        if cached is not None:
            return cached

        with self._lock:
            matched: tuple[Subscriber, ...] = ()
            for pattern_topic, subscribers in self._wildcard.items():
                if self._patterns[pattern_topic].match(data_topic):
                    matched += subscribers

            if len(self._match_cache) >= MATCH_CACHE_MAXSIZE:
                self._match_cache.clear()
            self._match_cache[data_topic] = matched
            return matched
