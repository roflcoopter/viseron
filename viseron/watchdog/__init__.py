"""Watchdog basclass."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from viseron.helpers import caller_name

LOGGER = logging.getLogger(__name__)


class WatchDog(ABC):
    """A watchdog for long running items."""

    registered_items: list = []
    started: bool = False

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
        if not cls.started:
            LOGGER.warning(
                f"Registering {item} while watchdog is not started. "
                f"Item IS NOT monitored properly. "
                f"Call came from: {caller_name()}, "
                "please report this as a bug on GitHub",
            )

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

    def stop(self):
        """Stop the watchdog."""
        LOGGER.debug("Stopping watchdog")
        # Clear the class-level registry, the same one register() appends to.
        # Assigning to self.registered_items would only create an instance
        # attribute and leave stale items in the shared registry.
        type(self).registered_items = []
