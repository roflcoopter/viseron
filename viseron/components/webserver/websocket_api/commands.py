"""WebSocket API commands."""
from __future__ import annotations

import logging
import os
import signal
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

import tornado
import voluptuous as vol

from viseron.components.webserver.auth import Group
from viseron.components.webserver.const import (
    WS_ERROR_NOT_FOUND,
    WS_ERROR_SAVE_CONFIG_FAILED,
)
from viseron.const import (
    CONFIG_PATH,
    EVENT_STATE_CHANGED,
    REGISTERED_DOMAINS,
    RESTART_EXIT_CODE,
)
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.exceptions import Unauthorized

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
    from viseron.states import EventStateChangedData

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


def require_admin(func):
    """Websocket decorator to require user to be an admin."""

    @wraps(func)
    def with_admin(connection: WebSocketHandler, message: dict[str, Any]) -> None:
        """Check admin and call function."""
        user = connection.current_user
        if user is None or not user.group == Group.ADMIN.value:
            raise Unauthorized()

        func(connection, message)

    return with_admin


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


@websocket_command(
    {
        vol.Required("type"): "unsubscribe_event",
        vol.Required("subscription"): int,
    }
)
def unsubscribe_event(connection: WebSocketHandler, message):
    """Unsubscribe to an event."""
    subscription = message["subscription"]
    if subscription in connection.subscriptions:
        connection.subscriptions.pop(subscription)()
        connection.send_message(result_message(message["command_id"]))
    else:
        connection.send_message(
            error_message(
                message["command_id"],
                WS_ERROR_NOT_FOUND,
                f"Subscription with command_id {message['subscription']} not found.",
            )
        )


@websocket_command(
    {
        vol.Required("type"): "subscribe_states",
        vol.Exclusive("entity_id", "entity"): str,
        vol.Exclusive("entity_ids", "entity"): [str],
    }
)
def subscribe_states(connection: WebSocketHandler, message):
    """Subscribe to state changes for one or multiple entities."""

    def forward_state_change(event: Event[EventStateChangedData]):
        """Forward state_changed event to WebSocket connection."""
        if "entity_id" in message:
            if event.data.entity_id == message["entity_id"]:
                connection.send_message(
                    message_to_json(event_message(message["command_id"], event))
                )
            return
        if event.data.entity_id in message["entity_ids"]:
            connection.send_message(
                message_to_json(event_message(message["command_id"], event))
            )
        return

    connection.subscriptions[message["command_id"]] = connection.vis.listen_event(
        EVENT_STATE_CHANGED,
        forward_state_change,
        ioloop=tornado.ioloop.IOLoop.current(),
    )
    connection.send_message(result_message(message["command_id"]))


@websocket_command(
    {
        vol.Required("type"): "unsubscribe_states",
        vol.Required("subscription"): int,
    }
)
def unsubscribe_states(connection: WebSocketHandler, message):
    """Unsubscribe to state changes."""
    message["type"] = "unsubscribe_event"
    unsubscribe_event(connection, message)


@websocket_command({vol.Required("type"): "get_cameras"})
def get_cameras(connection: WebSocketHandler, message):
    """Get all registered cameras."""
    connection.send_message(
        message_to_json(
            result_message(
                message["command_id"],
                connection.vis.data[REGISTERED_DOMAINS].get(CAMERA_DOMAIN, {}),
            ),
        )
    )


@websocket_command({vol.Required("type"): "get_config"})
def get_config(connection: WebSocketHandler, message):
    """Return config in text format."""
    with open(CONFIG_PATH, encoding="utf-8") as config_file:
        config = config_file.read()

    connection.send_message(
        result_message(
            message["command_id"],
            {"config": config},
        )
    )


@require_admin
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


@require_admin
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


@websocket_command({vol.Required("type"): "get_entities"})
def get_entities(connection: WebSocketHandler, message):
    """Get all registered entities."""
    connection.send_message(
        message_to_json(
            result_message(message["command_id"], connection.vis.get_entities()),
        )
    )
