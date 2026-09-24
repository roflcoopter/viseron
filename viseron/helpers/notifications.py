"""Notification helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.exceptions import DomainNotRegisteredError

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)


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
