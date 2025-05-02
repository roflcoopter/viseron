"""go2rtc component."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import requests
import voluptuous as vol
import yaml

from .const import COMPONENT, DESC_COMPONENT, GO2RTC_CONFIG

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): vol.Schema(
            {}, extra=vol.ALLOW_EXTRA
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config: dict[str, Any]) -> bool:
    """Set up the logger component."""
    vis.data[COMPONENT] = Go2RTC(vis, config)

    return True


class Go2RTC:
    """Go2RTC class."""

    def __init__(self, vis: Viseron, config: dict[str, Any]) -> None:
        """Initialize go2rtc."""
        self._vis = vis
        self._config = config

        self._create_config()
        self.restart()

    def _create_config(self):
        with open(GO2RTC_CONFIG, "w", encoding="utf-8") as config_file:
            yaml.dump(self._config[COMPONENT], config_file)

    def restart(self) -> None:
        """Restart the go2rtc."""
        LOGGER.debug("Restarting go2rtc")
        try:
            response = requests.post("http://localhost:1984/api/restart", timeout=5)
        except requests.RequestException as exc:
            LOGGER.error("Failed to restart go2rtc: %s", exc)
            return

        if response.status_code == 200:
            LOGGER.debug("Go2RTC restarted successfully")
        else:
            LOGGER.error("Failed to restart go2rtc: %s", response.text)
