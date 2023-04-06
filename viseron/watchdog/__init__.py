"""Watchdog basclass."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from apscheduler.schedulers import (
    SchedulerAlreadyRunningError,
    SchedulerNotRunningError,
)
from apscheduler.schedulers.background import BackgroundScheduler

LOGGER = logging.getLogger(__name__)


class WatchDog(ABC):
    """A watchdog for long running items."""

    registered_items: list = []
    _scheduler = BackgroundScheduler(timezone="UTC", daemon=True)

    def __init__(self) -> None:
        try:
            self._scheduler.start()
            LOGGER.debug("Starting scheduler")
        except SchedulerAlreadyRunningError:
            pass

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

    def stop(self) -> None:
        """Stop the watchdog."""
        try:
            self._scheduler.shutdown()
            LOGGER.debug("Stopping scheduler")
        except SchedulerNotRunningError:
            pass
