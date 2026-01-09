"""ONVIF Device API handler."""

import logging

from viseron.components.onvif.const import CONFIG_DEVICE
from viseron.components.webserver.api.v1.actions.onvif.base import (
    ActionsOnvifAPIHandler,
    action_handler,
)
from viseron.components.webserver.auth import Role

LOGGER = logging.getLogger(__name__)


class ActionsOnvifDeviceAPIHandler(ActionsOnvifAPIHandler):
    """ONVIF Device action handler."""

    @property
    def _service_name(self):
        """Get service name."""
        return CONFIG_DEVICE

    ONVIF_DEVICE_BASE_PATH = f"/actions/onvif/{CONFIG_DEVICE}"
    CAMERA_IDENTIFIER_REGEX = r"(?P<camera_identifier>[A-Za-z0-9_]+)"
    ACTION_REGEX = r"(?P<action>[a-z_]+)"

    routes = [
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                rf"{ONVIF_DEVICE_BASE_PATH}/{CAMERA_IDENTIFIER_REGEX}"
                rf"/{ACTION_REGEX}"
            ),
            "supported_methods": ["GET"],
            "method": "get_onvif_device",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                rf"{ONVIF_DEVICE_BASE_PATH}/{CAMERA_IDENTIFIER_REGEX}"
                rf"/{ACTION_REGEX}"
            ),
            "supported_methods": ["PUT"],
            "method": "put_onvif_device",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                rf"{ONVIF_DEVICE_BASE_PATH}/{CAMERA_IDENTIFIER_REGEX}"
                rf"/{ACTION_REGEX}"
            ),
            "supported_methods": ["POST"],
            "method": "post_onvif_device",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                rf"{ONVIF_DEVICE_BASE_PATH}/{CAMERA_IDENTIFIER_REGEX}"
                rf"/{ACTION_REGEX}"
            ),
            "supported_methods": ["DELETE"],
            "method": "delete_onvif_device",
        },
    ]

    @action_handler
    async def get_onvif_device(
        self,
        device_service,
        camera_identifier: str,
        action: str,
    ):
        """Handle GET requests for ONVIF Device actions."""

        if action == "information":
            await self.validate_action_response(
                await device_service.get_device_information(), action, camera_identifier
            )
            return

        if action == "scopes":
            await self.validate_action_response(
                await device_service.get_scopes(), action, camera_identifier
            )
            return

        if action == "capabilities":
            await self.validate_action_response(
                await device_service.get_capabilities(), action, camera_identifier
            )
            return

        if action == "services":
            await self.validate_action_response(
                await device_service.get_services(), action, camera_identifier
            )
            return

        if action == "users":
            await self.validate_action_response(
                await device_service.get_users(), action, camera_identifier
            )
            return

        if action == "system_date":
            await self.validate_action_response(
                await device_service.get_system_date_and_time(),
                action,
                camera_identifier,
            )
            return

        if action == "hostname":
            await self.validate_action_response(
                await device_service.get_hostname(), action, camera_identifier
            )
            return

        if action == "ntp":
            await self.validate_action_response(
                await device_service.get_ntp(), action, camera_identifier
            )
            return

        if action == "discovery_mode":
            await self.validate_action_response(
                await device_service.get_discovery_mode(), action, camera_identifier
            )
            return

        if action == "network_default_gateway":
            await self.validate_action_response(
                await device_service.get_network_default_gateway(),
                action,
                camera_identifier,
            )
            return

        if action == "network_interface":
            await self.validate_action_response(
                await device_service.get_network_interfaces(), action, camera_identifier
            )
            return

        if action == "network_protocols":
            await self.validate_action_response(
                await device_service.get_network_protocols(), action, camera_identifier
            )
            return

        if action == "dns":
            await self.validate_action_response(
                await device_service.get_dns(), action, camera_identifier
            )
            return

        self.unknown_action(action)

    @action_handler
    async def put_onvif_device(
        self,
        device_service,
        camera_identifier: str,
        action: str,
    ):
        """Handle PUT requests for ONVIF Device actions."""

        request_data = self.get_request_body()

        if action == "set_scopes":
            scopes = self.validate_request_data(request_data, "scopes")
            set_scopes = await device_service.set_scopes(scopes)
            await self.validate_action_status(set_scopes, action, camera_identifier)
            return

        if action == "set_system_date":
            system_date = self.validate_request_data(request_data, "system_date")
            set_system_date_and_time = await device_service.set_system_date_and_time(
                datetime_type=system_date.get("datetime_type"),
                daylight_savings=system_date.get("daylight_savings"),
                timezone=system_date.get("timezone"),
            )
            await self.validate_action_status(
                set_system_date_and_time, action, camera_identifier
            )
            return

        if action == "set_hostname":
            hostname = self.validate_request_data(request_data, "hostname")
            set_hostname = await device_service.set_hostname(hostname)
            await self.validate_action_status(set_hostname, action, camera_identifier)
            return

        if action == "set_ntp":
            ntp = self.validate_request_data(request_data, "ntp")
            set_ntp = await device_service.set_ntp(
                ntp_server=ntp.get("ntp_server"),
                from_dhcp=ntp.get("from_dhcp"),
                ntp_type=ntp.get("ntp_type"),
            )
            await self.validate_action_status(set_ntp, action, camera_identifier)
            return

        self.unknown_action(action)

    @action_handler
    async def post_onvif_device(
        self,
        device_service,
        camera_identifier: str,
        action: str,
    ):
        """Handle POST requests for ONVIF Device actions."""

        request_data = self.get_request_body()

        if action == "add_scopes":
            scopes = self.validate_request_data(request_data, "scopes")
            add_scopes = await device_service.add_scopes(scopes)
            await self.validate_action_status(add_scopes, action, camera_identifier)
            return

        if action == "create_users":
            users = self.validate_request_data(request_data, "users")
            create_users = await device_service.create_users(users)
            await self.validate_action_status(create_users, action, camera_identifier)
            return

        if action == "reboot":
            reboot = await device_service.system_reboot()
            await self.validate_action_status(reboot, action, camera_identifier)
            return

        self.unknown_action(action)

    @action_handler
    async def delete_onvif_device(
        self,
        device_service,
        camera_identifier: str,
        action: str,
    ):
        """Handle DELETE requests for ONVIF Device actions."""

        if action == "remove_scopes":
            required_query = "scopes"
            scopes = self.validate_query_parameter(
                self.get_query_argument(required_query, None), required_query
            )
            remove_scopes = await device_service.remove_scopes(scopes)
            await self.validate_action_status(remove_scopes, action, camera_identifier)
            return

        if action == "delete_users":
            required_query = "usernames"
            usernames = self.validate_query_parameter(
                self.get_query_argument(required_query, None), required_query
            )
            delete_users = await device_service.delete_users(usernames)
            await self.validate_action_status(delete_users, action, camera_identifier)
            return

        self.unknown_action(action)
