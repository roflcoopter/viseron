"""ONVIF Imaging API handler."""

import logging

from viseron.components.onvif.const import CONFIG_IMAGING
from viseron.components.webserver.api.v1.actions.onvif.base import (
    ActionsOnvifAPIHandler,
    action_handler,
)
from viseron.components.webserver.auth import Role

LOGGER = logging.getLogger(__name__)


class ActionsOnvifImagingAPIHandler(ActionsOnvifAPIHandler):
    """ONVIF Imaging action handler."""

    @property
    def _service_name(self):
        """Get service name."""
        return CONFIG_IMAGING

    ONVIF_IMAGING_BASE_PATH = f"/actions/onvif/{CONFIG_IMAGING}"
    CAMERA_IDENTIFIER_REGEX = r"(?P<camera_identifier>[A-Za-z0-9_]+)"
    ACTION_REGEX = r"(?P<action>[a-z_]+)"

    routes = [
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                rf"{ONVIF_IMAGING_BASE_PATH}/{CAMERA_IDENTIFIER_REGEX}"
                rf"/{ACTION_REGEX}"
            ),
            "supported_methods": ["GET"],
            "method": "get_onvif_imaging",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                rf"{ONVIF_IMAGING_BASE_PATH}/{CAMERA_IDENTIFIER_REGEX}"
                rf"/{ACTION_REGEX}"
            ),
            "supported_methods": ["PUT"],
            "method": "put_onvif_imaging",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                rf"{ONVIF_IMAGING_BASE_PATH}/{CAMERA_IDENTIFIER_REGEX}"
                rf"/{ACTION_REGEX}"
            ),
            "supported_methods": ["POST"],
            "method": "post_onvif_imaging",
        },
    ]

    @action_handler
    async def get_onvif_imaging(
        self,
        imaging_service,
        camera_identifier: str,
        action: str,
    ):
        """Handle GET requests for ONVIF Imaging actions."""

        if action == "settings":
            await self.validate_action_response(
                await imaging_service.get_imaging_settings(), action, camera_identifier
            )
            return

        if action == "options":
            await self.validate_action_response(
                await imaging_service.get_options(), action, camera_identifier
            )
            return

        if action == "move_options":
            await self.validate_action_response(
                await imaging_service.get_move_options(), action, camera_identifier
            )
            return

        self.unknown_action(action)

    @action_handler
    async def put_onvif_imaging(
        self,
        imaging_service,
        camera_identifier: str,
        action: str,
    ):
        """Handle PUT requests for ONVIF Imaging actions."""

        request_data = self.get_request_body()

        if action == "settings":
            settings = self.validate_request_data(request_data, "settings")
            force_persistence = self.validate_request_data(
                request_data, "force_persistence"
            )
            set_settings = await imaging_service.set_imaging_settings(
                settings, force_persistence
            )
            await self.validate_action_status(set_settings, action, camera_identifier)
            return

        if action == "brightness":
            brightness = self.validate_request_data(request_data, "brightness")
            force_persistence = self.validate_request_data(
                request_data, "force_persistence"
            )
            set_brightness = await imaging_service.set_brightness(
                brightness, force_persistence
            )
            await self.validate_action_status(set_brightness, action, camera_identifier)
            return

        self.unknown_action(action)

    @action_handler
    async def post_onvif_device(
        self,
        imaging_service,
        camera_identifier: str,
        action: str,
    ):
        """Handle POST requests for ONVIF Imaging actions."""

        request_data = self.get_request_body()

        if action == "move":
            focus = self.validate_request_data(request_data, "focus")
            move_focus = await imaging_service.move_focus(focus)
            await self.validate_action_status(move_focus, action, camera_identifier)
            return

        if action == "stop":
            stop_focus = await imaging_service.stop_focus()
            await self.validate_action_status(stop_focus, action, camera_identifier)
            return

        self.unknown_action(action)
