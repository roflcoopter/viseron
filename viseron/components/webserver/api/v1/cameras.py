"""Cameras API Handler."""

from __future__ import annotations

import logging
from http import HTTPStatus

from viseron.components.storage.orphaned_cameras import (
    OrphanedCameraError,
    OrphanedCameraUnavailableError,
    delete_orphaned_camera,
    get_orphaned_cameras,
)
from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.api.v1.camera import (
    NOTIFICATIONS_SCHEMA,
    set_notifications_paused,
)
from viseron.components.webserver.auth import Role

LOGGER = logging.getLogger(__name__)


class CamerasAPIHandler(BaseAPIHandler):
    """Handler for API calls related to cameras."""

    routes = [
        {
            "path_pattern": r"/cameras",
            "supported_methods": ["GET"],
            "method": "get_cameras_endpoint",
        },
        {
            "path_pattern": r"/cameras/failed",
            "supported_methods": ["GET"],
            "method": "get_failed_cameras_endpoint",
        },
        {
            "path_pattern": r"/cameras/orphaned",
            "supported_methods": ["GET"],
            "method": "get_orphaned_cameras_endpoint",
            "requires_role": [Role.ADMIN],
        },
        {
            "path_pattern": r"/cameras/orphaned/(?P<camera_identifier>[A-Za-z0-9_]+)",
            "supported_methods": ["DELETE"],
            "method": "delete_orphaned_camera_endpoint",
            "requires_role": [Role.ADMIN],
        },
        {
            "path_pattern": r"/cameras/notifications",
            "supported_methods": ["POST"],
            "method": "post_notifications_endpoint",
            "requires_role": [Role.ADMIN, Role.WRITE],
            "json_body_schema": NOTIFICATIONS_SCHEMA,
        },
    ]

    async def get_cameras_endpoint(self) -> None:
        """Return cameras."""
        await self.response_success(response=self._get_cameras() or {})

    async def get_failed_cameras_endpoint(self) -> None:
        """Return failed cameras."""
        await self.response_success(response=self._get_failed_cameras() or {})

    async def post_notifications_endpoint(self) -> None:
        """Pause or resume notifications for every camera the user can access."""
        for camera in (self._get_cameras() or {}).values():
            await self.run_in_executor(set_notifications_paused, camera, self.json_body)
        await self.response_success()

    async def get_orphaned_cameras_endpoint(self) -> None:
        """Return stored data for cameras that are no longer configured."""
        try:
            orphaned = await self.run_in_executor(
                get_orphaned_cameras, self._vis, self._storage
            )
        except OrphanedCameraUnavailableError as error:
            self.response_error(HTTPStatus.SERVICE_UNAVAILABLE, reason=str(error))
            return

        await self.response_success(
            response={"cameras": [camera.as_dict() for camera in orphaned]}
        )

    async def delete_orphaned_camera_endpoint(self, camera_identifier: str) -> None:
        """Delete all stored data for a camera that is no longer configured."""
        try:
            deleted = await self.run_in_executor(
                delete_orphaned_camera, self._vis, self._storage, camera_identifier
            )
        except OrphanedCameraUnavailableError as error:
            self.response_error(HTTPStatus.SERVICE_UNAVAILABLE, reason=str(error))
            return
        except OrphanedCameraError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, reason=str(error))
            return
        except OSError as error:
            LOGGER.error(
                f"Failed to delete orphaned camera {camera_identifier}: {error}",
                exc_info=True,
            )
            self.response_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                reason=f"Failed to delete camera {camera_identifier}",
            )
            return

        await self.response_success(response=deleted.as_dict())
