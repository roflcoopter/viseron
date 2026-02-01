"""ONVIF Media Actions API handler."""

import logging

from viseron.components.onvif.const import CONFIG_MEDIA
from viseron.components.webserver.api.v1.actions.onvif.base import (
    ActionsOnvifAPIHandler,
    action_handler,
)
from viseron.components.webserver.auth import Role

LOGGER = logging.getLogger(__name__)


class ActionsOnvifMediaAPIHandler(ActionsOnvifAPIHandler):
    """ONVIF Media action handler."""

    @property
    def _service_name(self):
        """Get service name."""
        return CONFIG_MEDIA

    ONVIF_MEDIA_BASE_PATH = f"/actions/onvif/{CONFIG_MEDIA}"
    CAMERA_IDENTIFIER_REGEX = r"(?P<camera_identifier>[A-Za-z0-9_]+)"
    ACTION_REGEX = r"(?P<action>[a-z_]+)"

    routes = [
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                rf"{ONVIF_MEDIA_BASE_PATH}/{CAMERA_IDENTIFIER_REGEX}"
                rf"/{ACTION_REGEX}"
            ),
            "supported_methods": ["GET"],
            "method": "get_onvif_media",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                rf"{ONVIF_MEDIA_BASE_PATH}/{CAMERA_IDENTIFIER_REGEX}"
                rf"/{ACTION_REGEX}"
            ),
            "supported_methods": ["PUT"],
            "method": "put_onvif_media",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                rf"{ONVIF_MEDIA_BASE_PATH}/{CAMERA_IDENTIFIER_REGEX}"
                rf"/{ACTION_REGEX}"
            ),
            "supported_methods": ["POST"],
            "method": "post_onvif_media",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                rf"{ONVIF_MEDIA_BASE_PATH}/{CAMERA_IDENTIFIER_REGEX}"
                rf"/{ACTION_REGEX}"
            ),
            "supported_methods": ["DELETE"],
            "method": "delete_onvif_media",
        },
    ]

    @action_handler
    async def get_onvif_media(
        self,
        media_service,
        camera_identifier: str,
        action: str,
    ):
        """Handle GET requests for ONVIF Media actions."""

        if action == "capabilities":
            await self.validate_action_response(
                await media_service.get_service_capabilities(),
                action,
                camera_identifier,
            )
            return

        if action == "profiles":
            await self.validate_action_response(
                await media_service.get_profiles(), action, camera_identifier
            )
            return

        if action == "profile":
            required_query = "token"
            token = self.validate_query_parameter(
                self.get_query_argument(required_query, None), required_query
            )
            await self.validate_action_response(
                await media_service.get_profile(token), action, camera_identifier
            )
            return

        if action == "stream_uri":
            token = self.get_query_argument("token", None)
            stream_type = self.get_query_argument("stream_type", None)
            protocol = self.get_query_argument("protocol", None)
            await self.validate_action_response(
                await media_service.get_stream_uri(token, stream_type, protocol),
                action,
                camera_identifier,
            )
            return

        if action == "snapshot_uri":
            token = self.get_query_argument("token", None)
            await self.validate_action_response(
                await media_service.get_snapshot_uri(token), action, camera_identifier
            )
            return

        if action == "video_encoder_configuration":
            token = self.get_query_argument("token", None)
            await self.validate_action_response(
                await media_service.get_video_encoder_configuration(token),
                action,
                camera_identifier,
            )
            return

        if action == "video_encoder_configuration_options":
            token = self.get_query_argument("token", None)
            await self.validate_action_response(
                await media_service.get_video_encoder_configuration_options(token),
                action,
                camera_identifier,
            )
            return

        if action == "audio_encoder_configuration":
            token = self.get_query_argument("token", None)
            await self.validate_action_response(
                await media_service.get_audio_encoder_configuration(token),
                action,
                camera_identifier,
            )
            return

        if action == "audio_encoder_configuration_options":
            token = self.get_query_argument("token", None)
            await self.validate_action_response(
                await media_service.get_audio_encoder_configuration_options(token),
                action,
                camera_identifier,
            )
            return

        self.unknown_action(action)

    @action_handler
    async def put_onvif_media(self, media_service, camera_identifier: str, action: str):
        """Handle PUT requests for ONVIF Media actions."""

        request_data = self.get_request_body()

        if action == "set_video_encoder_configuration":
            configuration = self.validate_request_data(request_data, "configuration")
            set_video_encoder_configuration = (
                await media_service.set_video_encoder_configuration(configuration)
            )
            await self.validate_action_status(
                set_video_encoder_configuration, action, camera_identifier
            )
            return

        if action == "set_audio_encoder_configuration":
            configuration = self.validate_request_data(request_data, "configuration")
            set_audio_encoder_configuration = (
                await media_service.set_audio_encoder_configuration(configuration)
            )
            await self.validate_action_status(
                set_audio_encoder_configuration, action, camera_identifier
            )
            return

        if action == "set_osd":
            osd = self.validate_request_data(request_data, "osd")
            set_osd = await media_service.set_osd(osd)
            await self.validate_action_status(set_osd, action, camera_identifier)
            return

        self.unknown_action(action)

    @action_handler
    async def post_onvif_media(
        self, media_service, camera_identifier: str, action: str
    ):
        """Handle POST requests for ONVIF Media actions."""

        request_data = self.get_request_body()

        if action == "create_profile":
            profile = self.validate_request_data(request_data, "profile")
            create_profile = await media_service.create_profile(
                name=profile.get("name"),
                token=profile.get("token", None),
            )
            await self.validate_action_status(create_profile, action, camera_identifier)
            return

        if action == "create_osd":
            osd = self.validate_request_data(request_data, "osd")
            create_osd = await media_service.create_osd(
                osd_config=osd,
            )
            await self.validate_action_status(create_osd, action, camera_identifier)
            return

        self.unknown_action(action)

    @action_handler
    async def delete_onvif_media(
        self, media_service, camera_identifier: str, action: str
    ):
        """Handle DELETE requests for ONVIF Media actions."""

        if action == "delete_profile":
            required_query = "profile_token"
            profile_token = self.validate_query_parameter(
                self.get_query_argument(required_query, None), required_query
            )
            delete_profile = await media_service.delete_profile(profile_token)
            await self.validate_action_status(delete_profile, action, camera_identifier)
            return

        if action == "delete_osd":
            required_query = "token"
            token = self.validate_query_parameter(
                self.get_query_argument(required_query, None), required_query
            )
            delete_osd = await media_service.delete_osd(token)
            await self.validate_action_status(delete_osd, action, camera_identifier)
            return

        self.unknown_action(action)
