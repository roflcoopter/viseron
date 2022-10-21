"""WebSocket API messages."""
from __future__ import annotations

import json
import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Dict

import voluptuous as vol

from viseron.components.webserver.const import TYPE_RESULT, WS_ERROR_UNKNOWN_ERROR
from viseron.helpers.json import JSONEncoder

if TYPE_CHECKING:
    from viseron import Event

LOGGER = logging.getLogger(__name__)

BASE_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required("command_id"): vol.Range(min=0),
    }
)

MINIMAL_MESSAGE_SCHEMA = BASE_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): str,
    },
    extra=vol.ALLOW_EXTRA,
)


def message_to_json(message: dict[str, Any]) -> str:
    """Serialize a websocket message to json."""
    try:
        return partial(json.dumps, cls=JSONEncoder, allow_nan=False)(message)
    except (ValueError, TypeError):
        LOGGER.error("Unable to serialize to JSON. ", exc_info=True)
        return partial(json.dumps, cls=JSONEncoder, allow_nan=False)(
            error_message(
                message["id"], WS_ERROR_UNKNOWN_ERROR, "Invalid JSON in response"
            )
        )


def result_message(command_id: int | None, result: Any = None) -> Dict[str, Any]:
    """Return an successful result message."""
    return {
        "command_id": command_id,
        "type": TYPE_RESULT,
        "success": True,
        "result": result,
    }


def error_message(command_id: int | None, code: str, message: str) -> Dict[str, Any]:
    """Return an error result message."""
    return {
        "command_id": command_id,
        "type": TYPE_RESULT,
        "success": False,
        "error": {"code": code, "message": message},
    }


def invalid_error_message(code: str, message: str) -> Dict[str, Any]:
    """Return an error result message for invalid messages."""
    return {
        "type": TYPE_RESULT,
        "success": False,
        "error": {"code": code, "message": message},
    }


def event_message(command_id: int, event: Event) -> dict[str, Any]:
    """Return an event message."""
    return {
        "command_id": command_id,
        "type": "event",
        "event": event,
    }
