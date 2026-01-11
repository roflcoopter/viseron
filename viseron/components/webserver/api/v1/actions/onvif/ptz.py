"""ONVIF PTZ API handler."""

import logging

import numpy as np

from viseron.components.onvif.const import CONFIG_PTZ
from viseron.components.webserver.api.v1.actions.onvif.base import (
    ActionsOnvifAPIHandler,
    action_handler,
)
from viseron.components.webserver.auth import Role

LOGGER = logging.getLogger(__name__)


class ActionsOnvifPtzAPIHandler(ActionsOnvifAPIHandler):
    """ONVIF PTZ action handler."""

    @property
    def _service_name(self):
        """Get service name."""
        return CONFIG_PTZ

    ONVIF_PTZ_BASE_PATH = f"/actions/onvif/{CONFIG_PTZ}"
    CAMERA_IDENTIFIER_REGEX = r"(?P<camera_identifier>[A-Za-z0-9_]+)"
    ACTION_REGEX = r"(?P<action>[a-z_]+)"

    routes = [
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                rf"{ONVIF_PTZ_BASE_PATH}/{CAMERA_IDENTIFIER_REGEX}" rf"/{ACTION_REGEX}"
            ),
            "supported_methods": ["GET"],
            "method": "get_onvif_ptz",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                rf"{ONVIF_PTZ_BASE_PATH}/{CAMERA_IDENTIFIER_REGEX}" rf"/{ACTION_REGEX}"
            ),
            "supported_methods": ["PUT"],
            "method": "put_onvif_ptz",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                rf"{ONVIF_PTZ_BASE_PATH}/{CAMERA_IDENTIFIER_REGEX}" rf"/{ACTION_REGEX}"
            ),
            "supported_methods": ["POST"],
            "method": "post_onvif_ptz",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                rf"{ONVIF_PTZ_BASE_PATH}/{CAMERA_IDENTIFIER_REGEX}" rf"/{ACTION_REGEX}"
            ),
            "supported_methods": ["DELETE"],
            "method": "delete_onvif_ptz",
        },
    ]

    @action_handler
    async def get_onvif_ptz(self, ptz_service, camera_identifier: str, action: str):
        """Handle GET requests for ONVIF PTZ actions."""

        if action == "user_config":
            await self.validate_action_response(
                ptz_service.get_ptz_config(), action, camera_identifier
            )
            return

        if action == "status":
            await self.validate_action_response(
                await ptz_service.get_status(), action, camera_identifier
            )
            return

        if action == "presets":
            await self.validate_action_response(
                await ptz_service.get_presets(), action, camera_identifier
            )
            return

        if action == "nodes":
            await self.validate_action_response(
                await ptz_service.get_nodes(), action, camera_identifier
            )
            return

        if action == "configurations":
            await self.validate_action_response(
                await ptz_service.get_configurations(), action, camera_identifier
            )
            return

        if action == "configuration_options":
            await self.validate_action_response(
                await ptz_service.get_configuration_options(), action, camera_identifier
            )
            return

        self.unknown_action(action)

    @action_handler
    async def put_onvif_ptz(self, ptz_service, camera_identifier: str, action: str):
        """Handle PUT requests for ONVIF PTZ actions."""

        request_data = self.get_request_body()

        if action == "set_home":
            set_home = await ptz_service.set_home_position()
            await self.validate_action_status(set_home, action, camera_identifier)
            return

        if action == "set_preset":
            preset_name = self.validate_request_data(request_data, "preset_name")
            set_preset = await ptz_service.set_preset(preset_name)
            await self.validate_action_status(set_preset, action, camera_identifier)
            return

        self.unknown_action(action)

    @action_handler
    async def post_onvif_ptz(self, ptz_service, camera_identifier: str, action: str):
        """Handle POST requests for ONVIF PTZ actions."""

        request_data = self.get_request_body()

        if action == "continuous_move":
            continuous = self.validate_request_data(request_data, "continuous")
            continuous_move = await ptz_service.continuous_move(
                x_velocity=continuous.get("x_velocity", 0.0),
                y_velocity=continuous.get("y_velocity", 0.0),
                zoom_velocity=continuous.get("zoom_velocity", 0.0),
                seconds=continuous.get("seconds", 0.0),
            )
            await self.validate_action_status(
                continuous_move, action, camera_identifier
            )
            return

        if action == "relative_move":
            relative = self.validate_request_data(request_data, "relative")
            relative_move = await ptz_service.relative_move(
                x_translation=relative.get("x_translation", 0.0),
                y_translation=relative.get("y_translation", 0.0),
                zoom_translation=relative.get("zoom_translation", 0.0),
                x_speed=relative.get("x_speed"),
                y_speed=relative.get("y_speed"),
                zoom_speed=relative.get("zoom_speed"),
            )
            await self.validate_action_status(relative_move, action, camera_identifier)
            return

        if action == "absolute_move":
            absolute = self.validate_request_data(request_data, "absolute")
            absolute_move = await ptz_service.absolute_move(
                x_position=absolute.get("x_position", 0.0),
                y_position=absolute.get("y_position", 0.0),
                zoom_position=absolute.get("zoom_position", 0.0),
                x_speed=absolute.get("x_speed"),
                y_speed=absolute.get("y_speed"),
                zoom_speed=absolute.get("zoom_speed"),
                is_adjusted=absolute.get("is_adjusted", False),
            )
            await self.validate_action_status(absolute_move, action, camera_identifier)
            return

        if action == "stop":
            stop = await ptz_service.stop()
            if not stop:
                # because some cameras do not support stop() operation,
                # try sending zero continuous move
                stop_with_zero_continuous = await ptz_service.continuous_move(
                    0.0, 0.0, 0.0, 1.0
                )
                await self.validate_action_status(
                    stop_with_zero_continuous, action, camera_identifier
                )
                return
            await self.validate_action_status(stop, action, camera_identifier)
            return

        if action == "home":
            home = await ptz_service.go_home_position()
            await self.validate_action_status(home, action, camera_identifier)
            return

        if action == "goto_preset":
            preset_token = self.validate_request_data(request_data, "preset_token")
            goto_preset = await ptz_service.goto_preset(preset_token)
            await self.validate_action_status(goto_preset, action, camera_identifier)
            return

        if action == "patrol":
            patrol = self.validate_request_data(request_data, "patrol")
            patrol_move = await ptz_service.patrol(
                duration=patrol.get("duration", 60),
                sleep_after_swing=patrol.get("sleep_after_swing", 6),
                step_size=patrol.get("step_size", 0.1),
                step_sleep_time=patrol.get("step_sleep_time", 0.1),
            )
            await self.validate_action_status(patrol_move, action, camera_identifier)
            return

        if action == "lissa_patrol":
            lissa_patrol = self.validate_request_data(request_data, "lissa_patrol")
            lissa_patrol_move = await ptz_service.lissajous_curve_patrol(
                pan_amp=lissa_patrol.get("pan_amp", 1.0),
                pan_freq=lissa_patrol.get("pan_freq", 0.1),
                tilt_amp=lissa_patrol.get("tilt_amp", 1.0),
                tilt_freq=lissa_patrol.get("tilt_freq", 0.1),
                phase_shift=lissa_patrol.get("phase_shift", np.pi / 2),
                step_sleep_time=lissa_patrol.get("step_sleep_time", 0.1),
            )
            await self.validate_action_status(
                lissa_patrol_move, action, camera_identifier
            )
            return

        if action == "stop_patrol":
            stop_patrol = ptz_service.stop_patrol()
            await self.validate_action_status(stop_patrol, action, camera_identifier)
            return

        self.unknown_action(action)

    @action_handler
    async def delete_onvif_ptz(self, ptz_service, camera_identifier: str, action: str):
        """Handle DELETE requests for ONVIF PTZ actions."""

        if action == "remove_preset":
            required_query = "preset_token"
            preset_token = self.validate_query_parameter(
                self.get_query_argument(required_query, None), required_query
            )
            remove_preset = await ptz_service.remove_preset(preset_token)
            await self.validate_action_status(remove_preset, action, camera_identifier)
            return

        self.unknown_action(action)
