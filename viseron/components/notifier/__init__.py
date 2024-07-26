"""Notifier interface."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from os.path import basename
from typing import TYPE_CHECKING

import voluptuous as vol
from telegram import Bot
from telegram.error import TelegramError

from viseron.const import EVENT_STATE_CHANGED
from viseron.helpers.validators import Maybe

from .const import (
    COMPONENT,
    CONFIG_SMTP_PASSWORD,
    CONFIG_SMTP_PORT,
    CONFIG_SMTP_RECIPIENTS,
    CONFIG_SMTP_SENDER,
    CONFIG_SMTP_SERVER,
    CONFIG_SMTP_USERNAME,
    CONFIG_TELEGRAM_BOT_TOKEN,
    CONFIG_TELEGRAM_CHAT_ID,
    DEFAULT_PORT,
    DESC_COMPONENT,
    DESC_SMTP_PASSWORD,
    DESC_SMTP_PORT,
    DESC_SMTP_RECIPIENTS,
    DESC_SMTP_SENDER,
    DESC_SMTP_SERVER,
    DESC_SMTP_USERNAME,
    DESC_TELEGRAM_BOT_TOKEN,
    DESC_TELEGRAM_CHAT_ID,
)

# from viseron.watchdog.thread_watchdog import RestartableThread


if TYPE_CHECKING:
    from viseron import Event, Viseron

    # from viseron.helpers.entity import Entity

LOGGER = logging.getLogger(__name__)

LABEL_SCHEMA = vol.Schema([str])

NOTIFIER_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): vol.Schema(
            vol.Any(  # Ensure at least one of SMTP or Telegram is configured
                vol.All(  # SMTP configuration
                    {
                        vol.Required(
                            CONFIG_SMTP_SERVER, description=DESC_SMTP_SERVER
                        ): str,
                        vol.Optional(
                            CONFIG_SMTP_PORT,
                            default=DEFAULT_PORT,
                            description=DESC_SMTP_PORT,
                        ): int,
                        vol.Required(
                            CONFIG_SMTP_USERNAME, description=DESC_SMTP_USERNAME
                        ): Maybe(str),
                        vol.Required(
                            CONFIG_SMTP_PASSWORD, description=DESC_SMTP_PASSWORD
                        ): Maybe(str),
                        vol.Required(
                            CONFIG_SMTP_RECIPIENTS, description=DESC_SMTP_RECIPIENTS
                        ): Maybe(str),
                        vol.Required(
                            CONFIG_SMTP_SENDER, description=DESC_SMTP_SENDER
                        ): Maybe(str),
                    },
                ),
                vol.All(  # Telegram configuration
                    {
                        vol.Required(
                            CONFIG_TELEGRAM_BOT_TOKEN,
                            description=DESC_TELEGRAM_BOT_TOKEN,
                        ): Maybe(str),
                        vol.Required(
                            CONFIG_TELEGRAM_CHAT_ID, description=DESC_TELEGRAM_CHAT_ID
                        ): Maybe(int),
                    },
                ),
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)

CAMERA_SCHEMA = vol.Schema(
    {
        vol.Optional("labels", description="Cameras"): LABEL_SCHEMA,
        vol.Required(
            "notifier", description="Notifier configuration for the camera"
        ): NOTIFIER_SCHEMA,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): vol.Schema(
            vol.All(
                {
                    vol.Required(
                        "cameras", description="Camera configurations"
                    ): vol.All([CAMERA_SCHEMA], vol.Length(min=1)),
                    # Include other global configurations here if necessary
                }
            )
        ),
    }
)


def setup(vis: Viseron, config) -> bool:
    """Set up the notifier component."""
    config = config[COMPONENT]
    notifier = Notifier(vis, config)
    if notifier.test_connection():
        notifier.listen()
    else:
        return False
    return True


class Notifier:
    """Notifier class."""

    def __init__(self, vis, config) -> None:
        self._vis = vis
        self._config = config
        self._object_was_detected = False
        self._client = smtplib.SMTP(
            host=self._config[CONFIG_SMTP_SERVER],
            port=self._config[CONFIG_SMTP_PORT],
            timeout=10,
        )
        vis.data[COMPONENT] = self

    async def test_connection(self) -> bool:
        """Test connection to SMTP and Telegram."""
        if self._config[CONFIG_SMTP_SERVER]:
            smtp_server = smtplib.SMTP(
                self._config[CONFIG_SMTP_SERVER], self._config[CONFIG_SMTP_PORT]
            )
            try:
                smtp_server.login(
                    self._config[CONFIG_SMTP_USERNAME],
                    self._config[CONFIG_SMTP_PASSWORD],
                )
            except smtplib.SMTPException:
                LOGGER.error("Failed to login to SMTP server")
                return False
            finally:
                smtp_server.close()
        if self._config[CONFIG_TELEGRAM_BOT_TOKEN]:
            bot = Bot(token=self._config[CONFIG_TELEGRAM_BOT_TOKEN])
            try:
                await bot.get_me()
            except TelegramError:
                LOGGER.error("Failed to connect to Telegram")
                return False
        return True

    def listen(self) -> None:
        """Start listening for object detection and recording events."""
        self._vis.listen_event(EVENT_STATE_CHANGED, self.state_changed)

    async def notify_telegram(self, event_data) -> None:
        """Send notification by Telegram."""
        bot_token = self._config[CONFIG_TELEGRAM_BOT_TOKEN]
        chat_id = self._config[CONFIG_TELEGRAM_CHAT_ID]
        bot = Bot(token=bot_token)
        label = event_data.data.previous_state.attributes["objects"][0].formatted[
            "label"
        ]
        await bot.send_photo(
            chat_id=chat_id,
            photo=open(
                event_data.data.previous_state.attributes["thumbnail_path"], "rb"
            ),
            caption=f"Camera: {event_data.data.entity_id} detected a {label}",
        )

    def notify_email(self, event_data) -> None:
        """Send notification by email."""
        try:
            self._client.connect(
                host=self._config[CONFIG_SMTP_SERVER],
                port=self._config[CONFIG_SMTP_PORT],
            )
            self._client.login(
                self._config[CONFIG_SMTP_USERNAME], self._config[CONFIG_SMTP_PASSWORD]
            )
            msg = MIMEMultipart()
            msg["From"] = self._config[CONFIG_SMTP_SENDER]
            msg["To"] = self._config[CONFIG_SMTP_RECIPIENTS]
            msg["Date"] = formatdate(localtime=True)
            msg[
                "Subject"
            ] = f"Person was detected on camera {event_data.data.entity_id}"
            detected_object = event_data.data.previous_state.attributes["objects"][0]
            label = detected_object.formatted["label"]
            conf = detected_object.formatted["confidence"]
            msg.attach(
                MIMEText(
                    f"Camera: {event_data.data.entity_id} detected a {label}",
                    "plain",
                ),
            )
            html = f"""
            <html>
                <head></head>
                <body>
                    <p>Camera: {event_data.data.entity_id} detected a {label} with score {conf}<br>
                    <img src="cid:thumbnail"><br>
                    </p>
                </body>
            </html>
            """
            msg.attach(
                MIMEText(
                    html,
                    "html",
                ),
            )
            with open(
                event_data.data.previous_state.attributes["thumbnail_path"], "rb"
            ) as fil:
                thumbnail = MIMEImage(
                    fil.read(),
                    Name=basename(
                        event_data.data.previous_state.attributes["thumbnail_path"]
                    ),
                )
                thumbnail.add_header("Content-ID", "<thumbnail>")
                thumbnail.add_header(
                    "Content-Disposition",
                    "inline",
                    filename=basename(
                        event_data.data.previous_state.attributes["thumbnail_path"]
                    ),
                )
                msg.attach(thumbnail)
            self._client.sendmail(
                from_addr=self._config[CONFIG_SMTP_SENDER],
                to_addrs=self._config[CONFIG_SMTP_RECIPIENTS],
                msg=msg.as_string(),
            )
        finally:
            self._client.close()

    def state_changed(self, event_data: Event) -> None:
        """Viseron state change listener."""
        LOGGER.info(event_data)
        if (
            event_data.data.entity_id.startswith("binary_sensor.")
            and event_data.data.entity_id.endswith("_recorder")
            and event_data.data.current_state
            and event_data.data.current_state.state == "off"
            and self._object_was_detected
        ):
            self._object_was_detected = False
            self.notify_email(event_data)
            asyncio.run(self.notify_telegram(event_data))
        elif (
            event_data.data.entity_id.endswith("_object_detected_person")
            and event_data.data.current_state
            and event_data.data.current_state.state == "on"
        ):
            self._object_was_detected = True

    def stop(self) -> None:
        """Stop notifier component."""
        LOGGER.info("Closing notifier component")
        self._client.close()
