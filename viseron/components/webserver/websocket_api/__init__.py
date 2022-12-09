"""Websocket API handler."""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Callable

import tornado.gen
import tornado.websocket
import voluptuous as vol
from tornado.ioloop import IOLoop
from tornado.queues import Queue
from voluptuous.humanize import humanize_error

from viseron.components.webserver.const import (
    WEBSOCKET_COMMANDS,
    WS_ERROR_INVALID_FORMAT,
    WS_ERROR_INVALID_JSON,
    WS_ERROR_OLD_COMMAND_ID,
    WS_ERROR_UNKNOWN_COMMAND,
    WS_ERROR_UNKNOWN_ERROR,
)

from .messages import MINIMAL_MESSAGE_SCHEMA, error_message, invalid_error_message

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)


class WebSocketHandler(tornado.websocket.WebSocketHandler):
    """Websocket handler."""

    def initialize(self, vis: Viseron):
        """Initialize websocket handler."""
        self.vis = vis
        self._last_id = 0
        self.subscriptions: dict[int, Callable[[], None]] = {}

        self._message_queue: Queue[str] = Queue()

    async def _write_message(self):
        """Write messages to client."""
        while True:
            if (message := await self._message_queue.get()) is None:
                break

            # LOGGER.debug("Sending message {message}".format(message=message))
            await self.write_message(message)
        LOGGER.debug("Exiting WebSocket message writer")

    def check_origin(self, _origin):
        """Check request origin."""
        return True

    def send_message(self, message):
        """Send message to client."""
        self._message_queue.put(message)

    async def async_send_message(self, message):
        """Send message to client."""
        await self._message_queue.put(message)

    async def handle_message(self, message):
        """Handle a single incoming message."""
        handlers = self.vis.data[WEBSOCKET_COMMANDS]

        try:
            message = MINIMAL_MESSAGE_SCHEMA(message)
        except vol.Invalid:
            LOGGER.error("Message incorrectly formatted: %s", message)
            await self.async_send_message(
                invalid_error_message(
                    WS_ERROR_INVALID_FORMAT,
                    "Message incorrectly formatted.",
                )
            )
            return

        command_id = message["command_id"]
        if command_id <= self._last_id:
            LOGGER.error("command_id values have to increase: %s", message)
            await self.async_send_message(
                error_message(
                    command_id,
                    WS_ERROR_OLD_COMMAND_ID,
                    "command_id values have to increase.",
                )
            )
            return

        if message["type"] not in handlers:
            LOGGER.error("Unknown command: {}".format(message["type"]))
            await self.async_send_message(
                error_message(command_id, WS_ERROR_UNKNOWN_COMMAND, "Unknown command.")
            )
            return

        handler, schema = handlers[message["type"]]

        try:
            handler(self, schema(message))
        except vol.Invalid as err:
            LOGGER.error(f"Message incorrectly formatted: {err}")
            await self.async_send_message(
                error_message(
                    command_id,
                    WS_ERROR_INVALID_FORMAT,
                    humanize_error(message, err),
                )
            )
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.error(f"Error handling message: {err}", exc_info=True)
            await self.async_send_message(
                error_message(command_id, WS_ERROR_UNKNOWN_ERROR, "Unknown error.")
            )
        self._last_id = command_id

    def open(self, *_args: str, **_kwargs: str):
        """Websocket open."""
        LOGGER.debug(f"WebSocket opened {self}")
        IOLoop.current().spawn_callback(self._write_message)

    def on_message(self, message):
        """Websocket message received."""
        LOGGER.debug("Received %s", message)
        try:
            message_data = json.loads(message)
        except ValueError:
            LOGGER.error("Invalid JSON message received.")
            self.send_message(
                invalid_error_message(
                    WS_ERROR_INVALID_JSON, "Invalid JSON message received"
                )
            )
            return
        IOLoop.current().spawn_callback(self.handle_message, message_data)

    def on_close(self):
        """Websocket close."""
        LOGGER.debug("WebSocket closed")
        for unsub in self.subscriptions.values():
            unsub()

        self._message_queue.put(None)
