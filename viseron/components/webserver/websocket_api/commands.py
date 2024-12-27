"""WebSocket API commands."""
from __future__ import annotations

import datetime
import enum
import logging
import os
import shutil
import signal
import uuid
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, overload

import tornado
import voluptuous as vol
from debouncer import DebounceOptions, debounce
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound

from viseron.components.storage.const import EVENT_FILE_CREATED, EVENT_FILE_DELETED
from viseron.components.storage.models import Motion, Objects, PostProcessorResults
from viseron.components.storage.queries import get_recording_fragments
from viseron.components.storage.util import EventFileCreated, EventFileDeleted
from viseron.components.webserver.auth import Group
from viseron.components.webserver.const import (
    DOWNLOAD_PATH,
    WS_ERROR_NOT_FOUND,
    WS_ERROR_SAVE_CONFIG_FAILED,
)
from viseron.components.webserver.download_token import DownloadToken
from viseron.const import (
    CONFIG_PATH,
    EVENT_STATE_CHANGED,
    REGISTERED_DOMAINS,
    RESTART_EXIT_CODE,
)
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.domains.camera.fragmenter import Fragment, get_available_timespans
from viseron.exceptions import Unauthorized
from viseron.helpers import create_directory, daterange_to_utc
from viseron.watchdog.thread_watchdog import RestartableThread

from .messages import (
    BASE_MESSAGE_SCHEMA,
    cancel_subscription_message,
    error_message,
    message_to_json,
    pong_message,
    result_message,
    subscription_result_message,
)

if TYPE_CHECKING:
    from viseron import Event
    from viseron.states import EventStateChangedData

    from . import WebSocketHandler

LOGGER = logging.getLogger(__name__)


@overload
def websocket_command(schema: dict[Any, Any]) -> Callable:
    ...


@overload
def websocket_command(schema: dict[Any, Any], command: str) -> Callable:
    ...


@overload
def websocket_command(schema: vol.Schema, command: str) -> Callable:
    ...


def websocket_command(
    schema: dict[Any, Any] | vol.Schema, command: str | None = None
) -> Callable:
    """Websocket command decorator."""
    if isinstance(schema, dict):
        if command is None:
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
        if connection.webserver.auth:
            user = connection.current_user
            if user is None or not user.group == Group.ADMIN:
                raise Unauthorized()

        func(connection, message)

    return with_admin


@websocket_command({vol.Required("type"): "ping"})
def ping(connection: WebSocketHandler, message) -> None:
    """Respond to ping."""
    connection.send_message(pong_message(message["command_id"]))


@websocket_command(
    {
        vol.Required("type"): "subscribe_event",
        vol.Required("event"): str,
        # Use only when not consuming the data, as the debounced events will be lost
        vol.Optional("debounce", default=None): vol.Maybe(vol.Any(float, int)),
    }
)
def subscribe_event(connection: WebSocketHandler, message) -> None:
    """Subscribe to an event."""

    def forward_event(event: Event) -> None:
        """Forward event to WebSocket connection."""
        connection.send_message(
            message_to_json(subscription_result_message(message["command_id"], event))
        )

    @debounce(
        wait=message["debounce"],
        options=DebounceOptions(  # pylint: disable=unexpected-keyword-arg
            time_window=message["debounce"],
        ),
    )
    def debounced_forward_event(event: Event) -> None:
        """Debounce forward event to WebSocket connection.

        Use only when the data is not of importance as information may be lost!
        """
        return forward_event(event)

    connection.subscriptions[message["command_id"]] = connection.vis.listen_event(
        message["event"],
        debounced_forward_event if message["debounce"] else forward_event,
        ioloop=tornado.ioloop.IOLoop.current(),
    )
    connection.send_message(result_message(message["command_id"]))


@websocket_command(
    {
        vol.Required("type"): "unsubscribe_event",
        vol.Required("subscription"): int,
    }
)
def unsubscribe_event(connection: WebSocketHandler, message) -> None:
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
def subscribe_states(connection: WebSocketHandler, message) -> None:
    """Subscribe to state changes for one or multiple entities."""

    def forward_state_change(event: Event[EventStateChangedData]) -> None:
        """Forward state_changed event to WebSocket connection."""
        if "entity_id" in message:
            if event.data.entity_id == message["entity_id"]:
                connection.send_message(
                    message_to_json(
                        subscription_result_message(message["command_id"], event)
                    )
                )
            return
        if "entity_ids" in message:
            if event.data.entity_id in message["entity_ids"]:
                connection.send_message(
                    message_to_json(
                        subscription_result_message(message["command_id"], event)
                    )
                )
            return
        connection.send_message(
            message_to_json(subscription_result_message(message["command_id"], event))
        )

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
def unsubscribe_states(connection: WebSocketHandler, message) -> None:
    """Unsubscribe to state changes."""
    message["type"] = "unsubscribe_event"
    unsubscribe_event(connection, message)


@websocket_command({vol.Required("type"): "get_cameras"})
def get_cameras(connection: WebSocketHandler, message) -> None:
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
def get_config(connection: WebSocketHandler, message) -> None:
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
def save_config(connection: WebSocketHandler, message) -> None:
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
def restart_viseron(connection: WebSocketHandler, message) -> None:
    """Restart Viseron."""
    connection.vis.exit_code = RESTART_EXIT_CODE
    os.kill(os.getpid(), signal.SIGINT)
    connection.send_message(
        result_message(
            message["command_id"],
        )
    )


@websocket_command({vol.Required("type"): "get_entities"})
def get_entities(connection: WebSocketHandler, message) -> None:
    """Get all registered entities."""
    connection.send_message(
        message_to_json(
            result_message(message["command_id"], connection.vis.get_entities()),
        )
    )


@websocket_command(
    command="subscribe_timespans",
    schema={
        vol.Required("type"): "subscribe_timespans",
        vol.Required("camera_identifiers"): [str],
        vol.Required("date"): vol.Any(str, None),
        vol.Optional("debounce", default=0.5): vol.Any(float, int),
    },
)
def subscribe_timespans(connection: WebSocketHandler, message) -> None:
    """Subscribe to cameras available timespans."""
    camera_identifiers: list[str] = message["camera_identifiers"]
    for camera_identifier in camera_identifiers:
        camera = connection.get_camera(camera_identifier)
        if camera is None:
            connection.send_message(
                error_message(
                    message["command_id"],
                    WS_ERROR_NOT_FOUND,
                    f"Camera with identifier {camera_identifier} not found.",
                )
            )
            return

    # Convert local start of day to UTC
    if date := message.get("date"):
        time_from, time_to = daterange_to_utc(date, connection.utc_offset)
    else:
        time_from = datetime.datetime(1970, 1, 1, 0, 0, 0)
        time_to = datetime.datetime(2999, 12, 31, 23, 59, 59, 999999)

    def send_timespans():
        """Send available timespans."""
        timespans = get_available_timespans(
            connection.get_session,
            camera_identifiers,
            time_from.timestamp(),
            time_to.timestamp(),
        )
        connection.send_message(
            message_to_json(
                subscription_result_message(
                    message["command_id"], {"timespans": timespans}
                )
            )
        )

    @debounce(
        wait=message["debounce"],
        options=DebounceOptions(  # pylint: disable=unexpected-keyword-arg
            time_window=message["debounce"],
        ),
    )
    def forward_timespans(
        _event: Event[EventFileCreated] | Event[EventFileDeleted],
    ) -> None:
        """Forward event to WebSocket connection."""
        send_timespans()

    subs = []
    for camera_identifier in camera_identifiers:
        subs.append(
            connection.vis.listen_event(
                EVENT_FILE_CREATED.format(
                    camera_identifier=camera_identifier,
                    category="recorder",
                    subcategory="segments",
                    file_name="*",
                ),
                forward_timespans,
                ioloop=tornado.ioloop.IOLoop.current(),
            )
        )
        subs.append(
            connection.vis.listen_event(
                EVENT_FILE_DELETED.format(
                    camera_identifier=camera_identifier,
                    category="recorder",
                    subcategory="segments",
                    file_name="*",
                ),
                forward_timespans,
                ioloop=tornado.ioloop.IOLoop.current(),
            )
        )

    def unsubscribe() -> None:
        """Unsubscribe."""
        for unsub in subs:
            unsub()

    connection.subscriptions[message["command_id"]] = unsubscribe
    connection.send_message(result_message(message["command_id"]))
    send_timespans()


@websocket_command(
    {
        vol.Required("type"): "unsubscribe_timespans",
        vol.Required("subscription"): int,
    }
)
def unsubscribe_timespans(connection: WebSocketHandler, message) -> None:
    """Unsubscribe to a cameras available timespans."""
    message["type"] = "unsubscribe_event"
    unsubscribe_event(connection, message)


@websocket_command(
    {
        vol.Required("type"): "export_recording",
        vol.Required("camera_identifier"): str,
        vol.Required("recording_id"): int,
    }
)
def export_recording(connection: WebSocketHandler, message) -> None:
    """Export a recording."""
    camera = connection.get_camera(message["camera_identifier"])
    if camera is None:
        connection.send_message(
            error_message(
                message["command_id"],
                WS_ERROR_NOT_FOUND,
                f"Camera with identifier {message['camera_identifier']} not found.",
            )
        )
        return

    ioloop = tornado.ioloop.IOLoop.current()

    def _result():
        files = get_recording_fragments(
            message["recording_id"],
            camera.recorder.lookback,
            connection.get_session,
        )
        fragments = [
            Fragment(
                file.filename, file.path, file.meta["m3u8"]["EXTINF"], file.orig_ctime
            )
            for file in files
            if file.meta.get("m3u8", False).get("EXTINF", False)
        ]
        recording = camera.fragmenter.concatenate_fragments(fragments)
        if not recording:
            connection.send_message(
                error_message(
                    message["command_id"],
                    WS_ERROR_NOT_FOUND,
                    "No fragments found for recording.",
                )
            )
            return

        create_directory(DOWNLOAD_PATH)
        new_path = os.path.join(DOWNLOAD_PATH, os.path.basename(recording))
        shutil.move(recording, new_path)

        download_token = DownloadToken(
            filename=new_path,
            token=str(uuid.uuid4()),
        )
        connection.webserver.download_tokens[download_token.token] = download_token

        ioloop.add_callback(
            connection.send_message,
            message_to_json(
                subscription_result_message(
                    message["command_id"],
                    {
                        "filename": download_token.filename,
                        "token": download_token.token,
                    },
                )
            ),
        )
        ioloop.add_callback(
            connection.send_message,
            message_to_json(cancel_subscription_message(message["command_id"])),
        )

    concat_thread = RestartableThread(
        name=f"viseron.camera.{message['camera_identifier']}.export_recording",
        target=_result,
        register=False,
    )
    concat_thread.start()
    connection.send_message(result_message(message["command_id"]))


class EventTypeModelEnum(enum.Enum):
    """Enum for event type string and their corresponding DB model."""

    MOTION = Motion
    OBJECT = Objects
    FACE_RECOGNITION = PostProcessorResults
    LICENSE_PLATE_RECOGNITION = PostProcessorResults


@websocket_command(
    {
        vol.Required("type"): "export_snapshot",
        vol.Required("event_type"): str,
        vol.Required("camera_identifier"): str,
        vol.Required("snapshot_id"): int,
    }
)
def export_snapshot(connection: WebSocketHandler, message) -> None:
    """Export a snapshot."""
    camera = connection.get_camera(message["camera_identifier"])
    if camera is None:
        connection.send_message(
            error_message(
                message["command_id"],
                WS_ERROR_NOT_FOUND,
                f"Camera with identifier {message['camera_identifier']} not found.",
            )
        )
        return

    try:
        model = EventTypeModelEnum[message["event_type"].upper()].value
    except KeyError:
        connection.send_message(
            error_message(
                message["command_id"],
                WS_ERROR_NOT_FOUND,
                f"Event type {message['event_type']} not found.",
            )
        )
        return

    with connection.get_session() as session:
        try:
            snapshot_path: str = session.execute(
                select(model.snapshot_path).where(model.id == message["snapshot_id"])
            ).scalar_one()
        except NoResultFound:
            connection.send_message(
                error_message(
                    message["command_id"],
                    WS_ERROR_NOT_FOUND,
                    f"Snapshot with id {message['snapshot_id']} not found.",
                )
            )
            return

    download_token = DownloadToken(
        filename=snapshot_path,
        token=str(uuid.uuid4()),
    )
    connection.webserver.download_tokens[download_token.token] = download_token

    connection.send_message(result_message(message["command_id"]))
    connection.send_message(
        message_to_json(
            subscription_result_message(
                message["command_id"],
                {
                    "filename": download_token.filename,
                    "token": download_token.token,
                },
            )
        )
    )
    connection.send_message(
        message_to_json(cancel_subscription_message(message["command_id"]))
    )
