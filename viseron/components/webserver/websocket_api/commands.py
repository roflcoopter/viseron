"""WebSocket API commands."""
from __future__ import annotations

import logging
import os
import signal
from typing import TYPE_CHECKING, Callable

import tornado
import voluptuous as vol

from viseron.components.webserver.const import WS_ERROR_SAVE_CONFIG_FAILED
from viseron.const import CONFIG_PATH, REGISTERED_DOMAINS, RESTART_EXIT_CODE
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN

from .messages import (
    BASE_MESSAGE_SCHEMA,
    error_message,
    event_message,
    message_to_json,
    pong_message,
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


@websocket_command({vol.Required("type"): "ping"})
def ping(connection: WebSocketHandler, message):
    """Respond to ping."""
    connection.send_message(pong_message(message["command_id"]))


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


@websocket_command({vol.Required("type"): "get_cameras"})
def get_cameras(connection: WebSocketHandler, message):
    """Get all registered cameras."""
    connection.send_message(
        result_message(
            message["command_id"],
            message_to_json(
                connection.vis.data[REGISTERED_DOMAINS].get(CAMERA_DOMAIN, {})
            ),
        )
    )


@websocket_command({vol.Required("type"): "get_config"})
def get_config(connection: WebSocketHandler, message):
    """Return config in text format."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as config_file:
        config = config_file.read()

    connection.send_message(
        result_message(
            message["command_id"],
            {"config": config},
        )
    )


@websocket_command({vol.Required("type"): "save_config", vol.Required("config"): str})
def save_config(connection: WebSocketHandler, message):
    """Save config to file."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as config_file:
            config_file.write(message["config"])
    except Exception as exception:  # pylint: disable=broad-except
        connection.send_message(
            error_message(
                message["command_id"],
                WS_ERROR_SAVE_CONFIG_FAILED,
                str(exception),
            )
        )
        return

    connection.send_message(
        result_message(
            message["command_id"],
        )
    )


@websocket_command({vol.Required("type"): "restart_viseron"})
def restart_viseron(connection: WebSocketHandler, message):
    """Restart Viseron."""
    connection.vis.exit_code = RESTART_EXIT_CODE
    os.kill(os.getpid(), signal.SIGINT)
    connection.send_message(
        result_message(
            message["command_id"],
        )
    )
