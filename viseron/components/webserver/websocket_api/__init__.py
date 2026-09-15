"""Websocket API handler."""

from __future__ import annotations

import asyncio
import json
import logging
from functools import partial
from typing import TYPE_CHECKING, Any

import tornado.websocket
import voluptuous as vol
from tornado.ioloop import IOLoop
from tornado.queues import Queue
from voluptuous.humanize import humanize_error

from viseron.components.webserver.auth import SessionExpiredError
from viseron.components.webserver.const import (
    WEBSOCKET_COMMANDS,
    WEBSOCKET_CONNECTIONS,
    WS_ERROR_INVALID_FORMAT,
    WS_ERROR_INVALID_JSON,
    WS_ERROR_OLD_COMMAND_ID,
    WS_ERROR_UNAUTHORIZED,
    WS_ERROR_UNKNOWN_COMMAND,
    WS_ERROR_UNKNOWN_ERROR,
)
from viseron.components.webserver.request_handler import ViseronRequestHandler
from viseron.exceptions import Unauthorized
from viseron.helpers.json import JSONEncoder

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
    from collections.abc import Callable

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

    def initialize(self, vis: Viseron) -> None:
        """Initialize websocket handler."""
        super().initialize(vis)
        self.vis = vis
        self._last_id = 0
        self.subscriptions: dict[int, Callable[[], None]] = {}

        self._message_queue: Queue[str | dict[str, Any] | None] = Queue()
        self._waiting_for_auth = True
        self._writer_task: asyncio.Task | None = None
        self._writer_exited = False
        self._session_id: str | None = None
        self._force_closing = False
        # Captured here so revocations arriving on other threads can schedule
        # work on the loop that actually serves this connection.
        self._connection_ioloop = IOLoop.current()

        self.vis.data[WEBSOCKET_CONNECTIONS].append(self)

    @property
    def session_id(self) -> str | None:
        """Return the id of the session this connection was authenticated with."""
        return self._session_id

    async def _write_message(self) -> None:
        """Write messages to client."""

        def _json_dumps(message):
            return partial(json.dumps, cls=JSONEncoder, allow_nan=False)(message)

        while True:
            if (message := await self._message_queue.get()) is None:
                break

            # LOGGER.debug("Sending message {message}".format(message=message))

            if isinstance(message, dict):
                try:
                    json_message = await self.run_in_executor(_json_dumps, message)
                    await self.write_message(json_message)
                except (ValueError, TypeError):
                    LOGGER.error(
                        f"Unable to serialize to JSON. Object: {message}", exc_info=True
                    )
                    await self.write_message(
                        error_message(
                            message["command_id"],
                            WS_ERROR_UNKNOWN_ERROR,
                            "Invalid JSON in response",
                        )
                    )
                continue
            await self.write_message(message)

        self._writer_exited = True
        LOGGER.debug("Exiting WebSocket message writer")

    def check_origin(self, origin):
        """Check request origin."""
        if self.settings.get("debug"):
            return True
        return super().check_origin(origin)

    def send_message(self, message) -> None:
        """Send message to client."""
        self.ioloop.add_callback(self.async_send_message, message)

    async def async_send_message(self, message) -> None:
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

        if not self.validate_access_token(access_token):
            return False

        if self.refresh_token is None:
            LOGGER.debug("No refresh token bound to the connection")
            return False

        self._session_id = self.refresh_token.session_id
        return True

    def validate_session(self) -> bool:
        """Return True if the session backing this connection is still valid.

        Authentication happens once at connection time, so without this the
        connection would outlive logout, password changes and session
        revocation for as long as the socket stays open.
        """
        auth = self._webserver.auth
        if not auth:
            return True

        if self._session_id is None:
            return False

        refresh_token = auth.get_refresh_token_by_session_id(self._session_id)
        if refresh_token is None:
            LOGGER.debug("Session has been revoked")
            return False

        try:
            auth.validate_refresh_token(refresh_token)
        except SessionExpiredError:
            LOGGER.debug("Session has expired")
            return False

        user = auth.get_user(refresh_token.user_id)
        if user is None or not user.enabled:
            LOGGER.debug("User not found or disabled")
            return False

        # Re-read so role and camera assignment changes take effect without
        # requiring a reconnect.
        self.current_user = user
        return True

    async def handle_message(self, message) -> None:
        """Handle a single incoming message."""
        if self._waiting_for_auth:
            if await self.run_in_executor(self.handle_auth, message):
                LOGGER.debug("Authentication successful")
                self._waiting_for_auth = False
                await self.async_send_message(auth_ok_message(self.vis))
                return
            LOGGER.warning("Authentication failed.")
            await self.async_send_message(
                auth_failed_message(
                    "Authentication failed.",
                )
            )
            await self.force_close()
            return

        if not await self.run_in_executor(self.validate_session):
            LOGGER.warning("Session is no longer valid, closing connection")
            await self.async_send_message(
                auth_failed_message("Session is no longer valid.")
            )
            await self.force_close()
            return

        try:
            message = await self.run_in_executor(MINIMAL_MESSAGE_SCHEMA, message)
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
            await handler(self, schema(message))
        except Exception as err:  # pylint: disable=broad-except
            await self.handle_exception(command_id, message, err)
        self._last_id = command_id

    async def handle_exception(self, command_id, message, err: Exception) -> None:
        """Handle an exception."""
        log_handler = LOGGER.error

        if isinstance(err, vol.Invalid):
            code = WS_ERROR_INVALID_FORMAT
            err_msg = humanize_error(message, err)
        elif isinstance(err, Unauthorized):
            code = WS_ERROR_UNAUTHORIZED
            err_msg = "Unauthorized."
        else:
            # Log unknown errors as exceptions
            log_handler = LOGGER.exception
            code = WS_ERROR_UNKNOWN_ERROR
            err_msg = "Unknown error"

        log_handler(
            "Error handling message. Error Code: %s, Error Message: %s, Message: %s",
            code,
            err_msg,
            message,
        )
        await self.async_send_message(
            error_message(
                command_id,
                code,
                err_msg,
            )
        )

    async def open(  # pylint: disable=invalid-overridden-method
        self, *_args: str, **_kwargs: str
    ) -> None:
        """Websocket open."""
        LOGGER.debug("WebSocket opened")
        if self._webserver.auth:
            self._waiting_for_auth = True
            await self.async_send_message(auth_required_message())
        else:
            await self.async_send_message(auth_not_required_message(self.vis))
            self._waiting_for_auth = False

        self._writer_task = asyncio.create_task(
            self._write_message(), name="WebSocketWriter"
        )

    async def on_message(  # pylint: disable=invalid-overridden-method
        self, message
    ) -> None:
        """Websocket message received."""
        LOGGER.debug(f"Received {message}")
        try:
            message_data = await self.run_in_executor(json.loads, message)
        except ValueError:
            LOGGER.error("Invalid JSON message received.")
            await self.async_send_message(
                invalid_error_message(
                    WS_ERROR_INVALID_JSON, "Invalid JSON message received"
                )
            )
            return
        await self.handle_message(message_data)

    def revoke_session(self) -> None:
        """Close the connection because its session was revoked.

        Safe to call from any thread.
        """
        self._connection_ioloop.add_callback(self._async_revoke_session)

    async def _async_revoke_session(self) -> None:
        """Notify the client that its session is gone and close the connection."""
        LOGGER.debug("Closing websocket for revoked session")
        await self.async_send_message(
            auth_failed_message("Session is no longer valid.")
        )
        await self.force_close()

    def _deregister(self) -> None:
        """Remove this connection from the registry of live connections."""
        connections = self.vis.data[WEBSOCKET_CONNECTIONS]
        if self in connections:
            connections.remove(self)

    async def force_close(self) -> None:
        """Close websocket."""
        if self._force_closing:
            return
        self._force_closing = True

        LOGGER.debug("Force close websocket")
        for unsub in self.subscriptions.values():
            unsub()
        self.subscriptions.clear()

        self._message_queue.put(None)
        # Wait until queue is empty
        while not (self._message_queue.empty() and self._writer_exited):
            if self._writer_task is None or self._writer_task.done():
                # A cancelled writer will never drain the queue, so waiting for
                # it would block forever.
                break
            await asyncio.sleep(0.5)
        self._deregister()
        self.close()
        LOGGER.debug("Force close finished")

    def on_close(self) -> None:
        """Websocket close."""
        LOGGER.debug("Websocket closed")
        for unsub in self.subscriptions.values():
            unsub()
        self.subscriptions.clear()

        self._message_queue.put(None)
        if self._writer_task:
            self._writer_task.cancel()
        self._deregister()
