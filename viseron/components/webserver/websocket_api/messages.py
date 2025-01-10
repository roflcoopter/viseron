"""WebSocket API messages."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from viseron.components.webserver.const import (
    TYPE_AUTH_FAILED,
    TYPE_AUTH_NOT_REQUIRED,
    TYPE_AUTH_OK,
    TYPE_AUTH_REQUIRED,
    TYPE_RESULT,
    TYPE_SUBSCRIPTION_RESULT,
)

if TYPE_CHECKING:
    from viseron import Event, Viseron

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


def system_information(vis: Viseron) -> dict[str, Any]:
    """Return system information."""
    return {
        "version": vis.version,
        "git_commit": vis.git_commit,
        "safe_mode": vis.safe_mode,
    }


def auth_ok_message(vis: Viseron) -> dict[str, Any]:
    """Return an auth_ok message."""
    return {
        "type": TYPE_AUTH_OK,
        "message": "Authentication successful.",
        "system_information": system_information(vis),
    }


def auth_required_message() -> dict[str, str]:
    """Return an auth_required message."""
    return {"type": TYPE_AUTH_REQUIRED, "message": "Authentication required."}


def auth_not_required_message(vis: Viseron) -> dict[str, Any]:
    """Return an auth_not_required message."""
    return {
        "type": TYPE_AUTH_NOT_REQUIRED,
        "message": "Authentication not required.",
        "system_information": system_information(vis),
    }


def auth_failed_message(message: str) -> dict[str, str]:
    """Return an auth_failed message."""
    return {"type": TYPE_AUTH_FAILED, "message": message}


def result_message(command_id: int | None, result: Any = None) -> dict[str, Any]:
    """Return a successful result message."""
    return {
        "command_id": command_id,
        "type": TYPE_RESULT,
        "success": True,
        "result": result,
    }


def error_message(command_id: int | None, code: str, message: str) -> dict[str, Any]:
    """Return an error result message."""
    return {
        "command_id": command_id,
        "type": TYPE_RESULT,
        "success": False,
        "error": {"code": code, "message": message},
    }


def invalid_error_message(code: str, message: str) -> dict[str, Any]:
    """Return an error result message for invalid messages."""
    return {
        "type": TYPE_RESULT,
        "success": False,
        "error": {"code": code, "message": message},
    }


def subscription_result_message(
    command_id: int, result: Event | dict[str, Any]
) -> dict[str, Any]:
    """Return a subscription result message."""
    return {
        "command_id": command_id,
        "type": TYPE_SUBSCRIPTION_RESULT,
        "success": True,
        "result": result,
    }


def subscription_error_message(
    command_id: int, code: str, message: str
) -> dict[str, Any]:
    """Return a subscription error message."""
    return {
        "command_id": command_id,
        "type": TYPE_SUBSCRIPTION_RESULT,
        "success": False,
        "error": {"code": code, "message": message},
    }


def cancel_subscription_message(command_id: int) -> dict[str, Any]:
    """Return a cancel subscription message."""
    return {"command_id": command_id, "type": "cancel_subscription"}


def pong_message(command_id: int) -> dict[str, Any]:
    """Return a pong message."""
    return {"command_id": command_id, "type": "pong"}
