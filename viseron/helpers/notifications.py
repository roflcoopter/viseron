"""Notification helpers."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final

import voluptuous as vol

from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.exceptions import DomainNotRegisteredError
from viseron.helpers import utcnow

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)

DATA_NOTIFICATION_CAMERAS: Final = "notification_cameras"


def register_notification_cameras(
    vis: Viseron, component: str, camera_identifiers: Iterable[str]
) -> None:
    """Register the cameras a notification component sends notifications for."""
    vis.data.setdefault(DATA_NOTIFICATION_CAMERAS, {})[component] = set(
        camera_identifiers
    )


def unregister_notification_cameras(vis: Viseron, component: str) -> None:
    """Unregister the cameras of a notification component."""
    vis.data.get(DATA_NOTIFICATION_CAMERAS, {}).pop(component, None)


def notifications_configured(vis: Viseron, camera_identifier: str) -> bool:
    """Return if any notification component sends notifications for a camera."""
    return any(
        camera_identifier in camera_identifiers
        for camera_identifiers in vis.data.get(DATA_NOTIFICATION_CAMERAS, {}).values()
    )


def notifications_paused(vis: Viseron, camera_identifier: str | None) -> bool:
    """Return if notifications for a camera are paused.

    Unknown cameras are never paused, so events without a camera still notify.
    """
    if camera_identifier is None:
        return False
    try:
        cameras = vis.get_registered_identifiers(CAMERA_DOMAIN)
    except DomainNotRegisteredError:
        return False
    camera = cameras.get(camera_identifier)
    if camera is None or not camera.notifications_paused:
        return False
    LOGGER.debug(f"Notifications for camera {camera_identifier} are paused, skipping")
    return True


def future_datetime(value: str) -> datetime:
    """Validate that value is a timezone aware ISO 8601 datetime in the future."""
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise vol.Invalid("Expected an ISO 8601 datetime") from error
    if parsed.tzinfo is None:
        raise vol.Invalid("Datetime must include a timezone")
    if parsed <= utcnow():
        raise vol.Invalid("Datetime must be in the future")
    return parsed


def set_notifications_paused(camera: AbstractCamera, body: dict) -> None:
    """Pause or resume notifications for a camera from a request body."""
    if body["action"] == "resume":
        camera.resume_notifications()
        return
    until = body.get("until")
    if (duration := body.get("duration")) is not None:
        until = utcnow() + timedelta(seconds=duration)
    camera.pause_notifications(until)
