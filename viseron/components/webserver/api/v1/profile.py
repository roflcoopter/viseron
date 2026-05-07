"""User profile API handlers."""

from __future__ import annotations

from http import HTTPStatus
from zoneinfo import available_timezones

import voluptuous as vol

from viseron.components.webserver.api.handlers import BaseAPIHandler, require_auth
from viseron.components.webserver.auth import (
    AccessTokenLimitExceededError,
    AccessTokenNotFoundError,
    InvalidDateFormatError,
    InvalidTimeFormatError,
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
                    vol.Optional("date_format", default=None): vol.Maybe(str),
                    vol.Optional("time_format", default=None): vol.Maybe(str),
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
        {
            "requires_role": [Role.ADMIN, Role.READ, Role.WRITE],
            "path_pattern": r"/profile/access_tokens",
            "supported_methods": ["GET"],
            "method": "get_profile_access_tokens",
        },
        {
            "requires_role": [Role.ADMIN, Role.READ, Role.WRITE],
            "path_pattern": r"/profile/access_tokens",
            "supported_methods": ["POST"],
            "method": "post_profile_access_tokens",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Optional("expires_at", default=None): vol.Maybe(
                        vol.Coerce(float)
                    ),
                }
            ),
        },
        {
            "requires_role": [Role.ADMIN, Role.READ, Role.WRITE],
            "path_pattern": r"/profile/access_tokens/(?P<token_id>[0-9a-f]{32})",
            "supported_methods": ["DELETE"],
            "method": "delete_profile_access_token",
        },
        {
            "requires_role": [Role.ADMIN, Role.READ, Role.WRITE],
            "path_pattern": r"/profile/revoke_all",
            "supported_methods": ["POST"],
            "method": "post_profile_revoke_all",
        },
    ]

    async def get_profile_available_timezones(self) -> None:
        """Return list of available timezones."""
        timezones = sorted(available_timezones())
        await self.response_success(response={"timezones": timezones})

    @require_auth
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
                self.auth.update_preferences,
                self.current_user.id,
                Preferences(
                    timezone=self.json_body["timezone"],
                    date_format=self.json_body["date_format"],
                    time_format=self.json_body["time_format"],
                ),
            )
        except UserDoesNotExistError as error:
            self.response_error(HTTPStatus.NOT_FOUND, reason=str(error))
            return
        except InvalidTimezoneError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, reason=str(error))
            return
        except InvalidDateFormatError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, reason=str(error))
            return
        except InvalidTimeFormatError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, reason=str(error))
            return

        await self.response_success()

    @require_auth
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
                self.auth.update_display_name,
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

    @require_auth
    async def get_profile_access_tokens(self) -> None:
        """Return all personal access tokens for the current user."""
        if not self.current_user:
            self.response_error(
                HTTPStatus.UNAUTHORIZED, reason="Authentication required"
            )
            return

        tokens = await self.run_in_executor(
            self.auth.get_access_tokens_for_user,
            self.current_user.id,
        )
        await self.response_success(
            response={"access_tokens": [t.as_dict() for t in tokens]}
        )

    @require_auth
    async def post_profile_access_tokens(self) -> None:
        """Create a new personal access token for the current user."""
        if not self.current_user:
            self.response_error(
                HTTPStatus.UNAUTHORIZED, reason="Authentication required"
            )
            return

        name = self.json_body.get("name", "").strip()
        if not name:
            self.response_error(
                HTTPStatus.BAD_REQUEST, reason="Token name cannot be empty"
            )
            return

        expires_at: float | None = self.json_body.get("expires_at")

        try:
            token, raw_token = await self.run_in_executor(
                self.auth.create_access_token,
                self.current_user.id,
                name,
                expires_at,
            )
        except ValueError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, reason=str(error))
            return
        except AccessTokenLimitExceededError as error:
            self.response_error(HTTPStatus.TOO_MANY_REQUESTS, reason=str(error))
            return

        await self.response_success(
            status=HTTPStatus.CREATED,
            response={**token.as_dict(), "token": raw_token},
        )

    @require_auth
    async def delete_profile_access_token(self, token_id: str) -> None:
        """Delete a personal access token belonging to the current user."""
        if not self.current_user:
            self.response_error(
                HTTPStatus.UNAUTHORIZED, reason="Authentication required"
            )
            return

        try:
            await self.run_in_executor(
                self.auth.delete_access_token,
                token_id,
                self.current_user.id,
            )
        except AccessTokenNotFoundError as error:
            self.response_error(HTTPStatus.NOT_FOUND, reason=str(error))
            return

        await self.response_success()

    @require_auth
    async def post_profile_revoke_all(self) -> None:
        """Revoke all sessions and personal access tokens for the current user."""
        if not self.current_user:
            self.response_error(
                HTTPStatus.UNAUTHORIZED, reason="Authentication required"
            )
            return

        await self.run_in_executor(
            self.auth.revoke_all_for_user,
            self.current_user.id,
        )
        await self.response_success()
