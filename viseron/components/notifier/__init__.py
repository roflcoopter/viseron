"""Notifier interface."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from telegram import Bot

from viseron.const import EVENT_STATE_CHANGED
from viseron.helpers.validators import CameraIdentifier, CoerceNoneToDict

from .const import (
    COMPONENT,
    CONFIG_CAMERAS,
    CONFIG_DETECTION_LABEL,
    CONFIG_SEND_THUMBNAIL,
    CONFIG_SEND_VIDEO,
    CONFIG_TELEGRAM_BOT_TOKEN,
    CONFIG_TELEGRAM_CHAT_IDS,
    DESC_CAMERAS,
    DESC_COMPONENT,
    DESC_DETECTION_LABEL,
    DESC_SEND_THUMBNAIL,
    DESC_SEND_VIDEO,
    DESC_TELEGRAM_BOT_TOKEN,
    DESC_TELEGRAM_CHAT_IDS,
)

if TYPE_CHECKING:
    from viseron import Event, Viseron

    # from viseron.helpers.entity import Entity

LOGGER = logging.getLogger(__name__)

CAMERA_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_SEND_THUMBNAIL, description=DESC_SEND_THUMBNAIL): bool,
        vol.Required(CONFIG_SEND_VIDEO, description=DESC_SEND_VIDEO): bool,
    },
    extra=vol.ALLOW_EXTRA,
)

# Define the CONFIG_SCHEMA
CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): {
            vol.Required(
                CONFIG_TELEGRAM_BOT_TOKEN, description=DESC_TELEGRAM_BOT_TOKEN
            ): str,
            vol.Required(
                CONFIG_TELEGRAM_CHAT_IDS, description=DESC_TELEGRAM_CHAT_IDS
            ): [int],
            vol.Optional(
                CONFIG_DETECTION_LABEL,
                description=DESC_DETECTION_LABEL,
                default="person",
            ): str,
            vol.Required(CONFIG_CAMERAS, description=DESC_CAMERAS): {
                CameraIdentifier(): vol.All(CoerceNoneToDict(), CAMERA_SCHEMA),
            },
        },
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config) -> bool:
    """Set up the notifier component."""
    config = config[COMPONENT]
    notifier = Notifier(vis, config)
    notifier.listen_for_vis_events()
    return True


class Notifier:
    """Notifier class."""

    def __init__(self, vis, config) -> None:
        self._vis = vis
        self._config = config
        vis.data[COMPONENT] = self

    def listen_for_vis_events(self) -> None:
        """Start listening for object detection and recording events."""
        self._vis.listen_event(EVENT_STATE_CHANGED, self.state_changed)

    async def notify_telegram(self, event_data) -> None:
        """Send notification by Telegram."""
        bot_token = self._config[CONFIG_TELEGRAM_BOT_TOKEN]
        chat_ids = self._config[CONFIG_TELEGRAM_CHAT_IDS]
        bot = Bot(token=bot_token)
        label = event_data.data.previous_state.attributes["objects"][0].label
        for chat_id in chat_ids:
            await bot.send_photo(
                chat_id=chat_id,
                photo=open(
                    event_data.data.previous_state.attributes["thumbnail_path"], "rb"
                ),
                caption=f"Camera: {event_data.data.entity_id} detected a {label}",
            )
            await bot.send_video(
                chat_id=chat_id,
                video=open(event_data.data.previous_state.attributes["path"], "rb"),
                caption="Here's the video, yo.",
            )

    def state_changed(self, event_data: Event) -> None:
        """Viseron state change listener."""
        if (
            event_data.data.entity_id.startswith("binary_sensor.")
            and event_data.data.entity_id.endswith("_recorder")
            and event_data.data.current_state
            and event_data.data.current_state.state == "off"
            and event_data.data.previous_state
            and event_data.data.previous_state.state == "on"
            and len(event_data.data.previous_state.attributes["objects"]) > 0
            and event_data.data.previous_state.attributes["objects"][0].label
            == self._config[CONFIG_DETECTION_LABEL]
        ):
            LOGGER.info(
                f"Camera stopped recording a {self._config[CONFIG_DETECTION_LABEL]}"
                "sending telegram notification"
            )
            asyncio.run(self.notify_telegram(event_data))

    def stop(self) -> None:
        """Stop notifier component."""
        LOGGER.info("Closing notifier component")
