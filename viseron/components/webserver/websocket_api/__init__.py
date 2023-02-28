"""Websocket API handler."""
from __future__ import annotations

import asyncio
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
    WEBSOCKET_CONNECTIONS,
    WS_ERROR_INVALID_FORMAT,
    WS_ERROR_INVALID_JSON,
    WS_ERROR_OLD_COMMAND_ID,
    WS_ERROR_UNKNOWN_COMMAND,
    WS_ERROR_UNKNOWN_ERROR,
)
from viseron.components.webserver.request_handler import ViseronRequestHandler

from .messages import (
    MINIMAL_MESSAGE_SCHEMA,
    auth_failed_message,
    auth_not_required_message,
    auth_ok_message,
    auth_required_message,
    error_message,
    invalid_error_message,
)

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)

AUTH_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required("type"): "auth",
        vol.Required("access_token"): str,
    }
)


class WebSocketHandler(ViseronRequestHandler, tornado.websocket.WebSocketHandler):
    """Websocket handler."""

    def initialize(self, vis: Viseron):
        """Initialize websocket handler."""
        super().initialize(vis)
        self.vis = vis
        self._last_id = 0
        self.subscriptions: dict[int, Callable[[], None]] = {}

        self._message_queue: Queue[str] = Queue()
        self._waiting_for_auth = True
        self._writer_exited = False

        self.vis.data[WEBSOCKET_CONNECTIONS].append(self)

    async def _write_message(self):
        """Write messages to client."""
        while True:
            if (message := await self._message_queue.get()) is None:
                break

            # LOGGER.debug("Sending message {message}".format(message=message))
            await self.write_message(message)
        self._writer_exited = True
        LOGGER.debug("Exiting WebSocket message writer")

    def check_origin(self, origin):
        """Check request origin."""
        if self.settings.get("debug"):
            return True
        return super().check_origin(origin)

    def send_message(self, message):
        """Send message to client."""
        self._message_queue.put(message)

    async def async_send_message(self, message):
        """Send message to client."""
        await self._message_queue.put(message)

    def handle_auth(self, message):
        """Handle auth message."""
        try:
            message = AUTH_MESSAGE_SCHEMA(message)
        except vol.Invalid as err:
            LOGGER.warning(
                "Auth message incorrectly formatted: %s", humanize_error(message, err)
            )
            return False

        signature = self.get_secure_cookie("signature_cookie")
        if signature is None:
            LOGGER.debug("Signature cookie is missing")
            return False

        access_token = f"{message['access_token']}.{signature.decode()}"

        return self.validate_access_token(access_token)

    async def handle_message(self, message):
        """Handle a single incoming message."""
        if self._waiting_for_auth:
            if await self.run_in_executor(self.handle_auth, message):
                LOGGER.debug("Authentication successful.")
                self._waiting_for_auth = False
                await self.async_send_message(auth_ok_message())
                return
            LOGGER.warning("Authentication failed.")
            await self.async_send_message(
                auth_failed_message(
                    "Authentication failed.",
                )
            )
            await self.force_close()
            return

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

        handlers = self._vis.data[WEBSOCKET_COMMANDS]
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
        LOGGER.debug("WebSocket opened")
        if self._webserver.auth:
            self._waiting_for_auth = True
            IOLoop.current().spawn_callback(self.send_message, auth_required_message())
        else:
            IOLoop.current().spawn_callback(
                self.send_message, auth_not_required_message()
            )
            self._waiting_for_auth = False
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

    async def force_close(self):
        """Close websocket."""
        LOGGER.debug("Force close websocket")
        for unsub in self.subscriptions.values():
            unsub()

        self._message_queue.put(None)
        # Wait until queue is empty
        while True:
            if self._message_queue.empty() and self._writer_exited:
                break
            await asyncio.sleep(0.5)
        self.vis.data[WEBSOCKET_CONNECTIONS].remove(self)
        LOGGER.debug("Force close finished")

    def on_close(self):
        """Websocket close."""
        LOGGER.debug("Websocket closed")
        for unsub in self.subscriptions.values():
            unsub()

        self._message_queue.put(None)
        self.vis.data[WEBSOCKET_CONNECTIONS].remove(self)
