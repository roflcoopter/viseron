"""User profile API handlers."""

from __future__ import annotations

from http import HTTPStatus
from zoneinfo import available_timezones

import voluptuous as vol

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import (
    InvalidTimezoneError,
    Preferences,
    Role,
    UserDoesNotExistError,
)


class ProfileAPIHandler(BaseAPIHandler):
    """User profile API handler."""

    routes = [
        {
            "path_pattern": r"/profile/available_timezones",
            "supported_methods": ["GET"],
            "method": "get_profile_available_timezones",
        },
        {
            "requires_role": [Role.ADMIN, Role.READ, Role.WRITE],
            "path_pattern": r"/profile/preferences",
            "supported_methods": ["PUT"],
            "method": "put_profile_preferences",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("timezone"): vol.Maybe(str),
                }
            ),
        },
        {
            "requires_role": [Role.ADMIN, Role.READ, Role.WRITE],
            "path_pattern": r"/profile/display_name",
            "supported_methods": ["PUT"],
            "method": "put_profile_display_name",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("name"): str,
                }
            ),
        },
    ]

    async def get_profile_available_timezones(self) -> None:
        """Return list of available timezones."""
        timezones = sorted(available_timezones())
        await self.response_success(response={"timezones": timezones})

    async def put_profile_preferences(self) -> None:
        """Update the current user's preferences."""
        if not self.current_user:
            self.response_error(
                HTTPStatus.UNAUTHORIZED,
                reason="Authentication required",
            )
            return

        try:
            await self.run_in_executor(
                self._webserver.auth.update_preferences,
                self.current_user.id,
                Preferences(timezone=self.json_body["timezone"]),
            )
        except UserDoesNotExistError as error:
            self.response_error(HTTPStatus.NOT_FOUND, reason=str(error))
            return
        except InvalidTimezoneError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, reason=str(error))
            return

        await self.response_success()

    async def put_profile_display_name(self) -> None:
        """Update the current user's display name."""
        if not self.current_user:
            self.response_error(
                HTTPStatus.UNAUTHORIZED,
                reason="Authentication required",
            )
            return

        name = self.json_body["name"].strip()
        if not name:
            self.response_error(
                HTTPStatus.BAD_REQUEST,
                reason="Name cannot be empty",
            )
            return

        try:
            await self.run_in_executor(
                self._webserver.auth.update_display_name,
                self.current_user.id,
                name,
            )
        except UserDoesNotExistError as error:
            self.response_error(HTTPStatus.NOT_FOUND, reason=str(error))
            return
        except ValueError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, reason=str(error))
            return

        await self.response_success()
