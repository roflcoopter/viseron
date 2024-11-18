"""Watchdog basclass."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

LOGGER = logging.getLogger(__name__)


class WatchDog(ABC):
    """A watchdog for long running items."""

    registered_items: list = []

    def __init__(self) -> None:
        """Initialize the watchdog."""

    @classmethod
    def register(
        cls,
        item,
    ) -> None:
        """Register item in the watchdog."""
        LOGGER.debug(f"Registering {item} in the watchdog")
        cls.registered_items.append(item)

    @classmethod
    def unregister(
        cls,
        item,
    ) -> None:
        """Unregister item from the watchdog."""
        LOGGER.debug(f"Removing {item} from the watchdog")
        try:
            cls.registered_items.remove(item)
        except ValueError:
            pass

    @abstractmethod
    def watchdog(self):
        """Watchdog."""
