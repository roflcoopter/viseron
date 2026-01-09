"""Base ONVIF API handler."""

from __future__ import annotations

import functools
import json
import logging
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, TypeAlias

from viseron.components.onvif import ONVIF
from viseron.components.onvif.const import (
    COMPONENT as ONVIF_COMPONENT,
    CONFIG_DEVICE,
    CONFIG_IMAGING,
    CONFIG_MEDIA,
    CONFIG_PTZ,
)
from viseron.components.onvif.utils import to_dict
from viseron.components.webserver.api.handlers import BaseAPIHandler

LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from viseron.components.onvif.device import Device
    from viseron.components.onvif.imaging import Imaging
    from viseron.components.onvif.media import Media
    from viseron.components.onvif.ptz import PTZ

ServiceType: TypeAlias = "Device | Media | Imaging | PTZ"


def action_handler(func):
    """Handle operation service retrieval and error handling."""

    @functools.wraps(func)
    async def wrapper(self, camera_identifier: str, action: str) -> None:
        # pylint: disable=protected-access
        service = self.get_service(self._service_name, camera_identifier)
        if service is None:
            return

        try:
            await func(self, service, camera_identifier, action)
        except (AttributeError, ValueError, RuntimeError) as error:
            LOGGER.error(
                f"Error executing {self._service_name.upper()} action {action} for "
                f"{camera_identifier}: {error}"
            )
            self.response_error(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                reason=(
                    f"Error executing {self._service_name.upper()} action {action} for "
                    f"{camera_identifier}: {str(error)}"
                ),
            )

    return wrapper


class ActionsOnvifAPIHandler(BaseAPIHandler):
    """Base ONVIF action handler."""

    # Just a placeholder (do not remove it!)
    @property
    def _service_name(self):
        return "base_service"

    def get_service(self, service: str, camera_identifier: str) -> ServiceType | None:
        """Get service for camera or send error response."""
        if ONVIF_COMPONENT not in self._vis.data:
            self.response_error(
                status_code=HTTPStatus.BAD_REQUEST,
                reason="ONVIF component not initialized.",
            )
            return None

        onvif_component: ONVIF = self._vis.data[ONVIF_COMPONENT]

        service_instance: ServiceType | None = None

        if service == CONFIG_DEVICE:
            service_instance = onvif_component.get_device_service(camera_identifier)
        elif service == CONFIG_MEDIA:
            service_instance = onvif_component.get_media_service(camera_identifier)
        elif service == CONFIG_IMAGING:
            service_instance = onvif_component.get_imaging_service(camera_identifier)
        elif service == CONFIG_PTZ:
            service_instance = onvif_component.get_ptz_service(camera_identifier)

        if service_instance is None:
            self.response_error(
                status_code=HTTPStatus.BAD_REQUEST,
                reason=f"No {service.upper()} service for {camera_identifier}",
            )
            return None

        return service_instance

    def get_request_body(self) -> dict:
        """Parse and return the JSON body of the request."""
        try:
            return json.loads(self.request.body)
        except json.JSONDecodeError:
            self.response_error(
                status_code=HTTPStatus.BAD_REQUEST,
                reason="Invalid JSON in request body.",
            )
            return {}

    def validate_request_data(self, request_data: dict, required_field: str):
        """Validate that required fields are present in the request data."""
        if required_field not in request_data:
            self.response_error(
                status_code=HTTPStatus.BAD_REQUEST,
                reason=f"Missing '{required_field}' in request body.",
            )
            return
        return request_data[required_field]

    def validate_query_parameter(self, parameter_value: Any, parameter_name: str):
        """Validate that required query parameters are present."""
        if parameter_value is None:
            self.response_error(
                status_code=HTTPStatus.BAD_REQUEST,
                reason=f"Missing '{parameter_name}' query parameter.",
            )
            return
        return parameter_value

    async def validate_action_response(
        self, response_data: Any, action: str, camera_identifier: str
    ):
        """Validate the response of an action and send error if failed."""
        if response_data is False or response_data is None:
            self.response_error(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                reason=(
                    f"Failed to get {self._service_name.upper()} {action} "
                    f"for {camera_identifier}."
                ),
            )
            return
        await self.response_success(response={f"{action}": to_dict(response_data)})
        return

    async def validate_action_status(
        self, status: bool, action: str, camera_identifier: str
    ):
        """Validate the status of an action and send error if failed."""
        if not status:
            self.response_error(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                reason=(
                    f"Failed to send {self._service_name.upper()} {action} "
                    f"command for {camera_identifier}."
                ),
            )
            return
        await self.response_success(
            response={
                "result": f"{self._service_name.upper()} {action} command "
                f"sent to {camera_identifier}",
            }
        )
        return

    def unknown_action(self, action: str):
        """Catch unknown action from service."""
        self.response_error(
            status_code=HTTPStatus.BAD_REQUEST,
            reason=f"Unknown action: {self._service_name.upper()} {action}",
        )
        return
