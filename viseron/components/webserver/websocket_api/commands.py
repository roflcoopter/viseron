"""WebSocket API commands."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

import tornado
import voluptuous as vol

from .messages import (
    BASE_MESSAGE_SCHEMA,
    event_message,
    message_to_json,
    result_message,
)

if TYPE_CHECKING:
    from viseron import Event

    from . import WebSocketHandler

LOGGER = logging.getLogger(__name__)


def websocket_command(
    schema: vol.Schema,
) -> Callable:
    """Websocket command decorator."""
    command = schema["type"]

    def decorate(func):
        """Decorate websocket command function."""
        setattr(func, "command", command)
        setattr(func, "schema", BASE_MESSAGE_SCHEMA.extend(schema))
        return func

    return decorate


@websocket_command(
    {vol.Required("type"): "subscribe_event", vol.Required("event"): str}
)
def subscribe_event(connection: WebSocketHandler, message):
    """Subscribe to an event."""

    def forward_event(event: Event):
        """Forward event to WebSocket connection."""
        connection.send_message(
            message_to_json(event_message(message["command_id"], event))
        )

    connection.subscriptions[message["command_id"]] = connection.vis.listen_event(
        message["event"], forward_event, ioloop=tornado.ioloop.IOLoop.current()
    )
    connection.send_message(result_message(message["command_id"]))
