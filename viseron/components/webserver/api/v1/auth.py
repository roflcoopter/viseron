"""Auth API Handlers."""
from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any, Literal

import voluptuous as vol

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import (
    AuthenticationFailed,
    InvalidRoleError,
    LastAdminUserError,
    Role,
    UserDoesNotExistError,
    UserExistsError,
    token_response,
)

LOGGER = logging.getLogger(__name__)


class AuthAPIHandler(BaseAPIHandler):
    """Handler for API calls related to authentication."""

    routes = [
        {
            "requires_auth": False,
            "path_pattern": r"/auth/enabled",
            "supported_methods": ["GET"],
            "method": "auth_enabled",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/auth/create",
            "supported_methods": ["POST"],
            "method": "auth_create",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Required("role"): vol.In([e.value for e in Role]),
                }
            ),
        },
        {
            "path_pattern": r"/auth/user/(?P<user_id>[A-Za-z0-9_]+)",
            "supported_methods": ["GET"],
            "method": "auth_user",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/auth/user/(?P<user_id>[A-Za-z0-9_]+)",
            "supported_methods": ["DELETE"],
            "method": "auth_delete",
        },
        {
            "requires_auth": False,
            "path_pattern": r"/auth/login",
            "supported_methods": ["POST"],
            "method": "auth_login",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Required("client_id"): str,
                }
            ),
        },
        {
            "requires_role": [Role.ADMIN, Role.READ, Role.WRITE],
            "path_pattern": r"/auth/logout",
            "supported_methods": ["POST"],
            "method": "auth_logout",
        },
        {
            "requires_auth": False,
            "path_pattern": r"/auth/token",
            "supported_methods": ["POST"],
            "method": "auth_token",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("grant_type", msg="Invalid grant_type"): vol.All(
                        vol.In(["refresh_token"]), str
                    ),
                    vol.Required("client_id"): str,
                }
            ),
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/auth/users",
            "supported_methods": ["GET"],
            "method": "auth_users",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": (
                r"/auth/user/(?P<user_id>[A-Za-z0-9_]+)/admin_change_password"
            ),
            "supported_methods": ["PUT"],
            "method": "auth_admin_change_password",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("new_password"): str,
                }
            ),
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/auth/user/(?P<user_id>[A-Za-z0-9_]+)",
            "supported_methods": ["PUT"],
            "method": "auth_update_user",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("username"): str,
                    vol.Required("role"): vol.In([e.value for e in Role]),
                }
            ),
        },
    ]

    async def auth_enabled(self) -> None:
        """Return if auth is enabled."""
        response = {
            "enabled": bool(self._webserver.auth) if self._webserver.auth else False,
            "onboarding_complete": await self.run_in_executor(
                self._webserver.auth.onboarding_complete
            )
            if self._webserver.auth
            else False,
        }
        await self.response_success(response=response)

    async def auth_create(self) -> None:
        """Create a new user."""
        try:
            await self.run_in_executor(
                self._webserver.auth.add_user,
                self.json_body["name"].strip(),
                self.json_body["username"].strip().casefold(),
                self.json_body["password"],
                Role(self.json_body["role"]),
            )
        except UserExistsError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, reason=str(error))
            return
        await self.response_success()

    async def auth_user(self, user_id: str) -> None:
        """Get a user.

        Returns 200 OK with user data if user exists.
        """
        user = await self.run_in_executor(self._webserver.auth.get_user, user_id)
        if user is None:
            self.response_error(HTTPStatus.NOT_FOUND, reason="User not found")
            return
        await self.response_success(
            response={
                "name": user.name,
                "username": user.username,
                "role": user.role.value,
            }
        )

    async def auth_delete(self, user_id: str) -> None:
        """Delete a user."""
        if self.current_user and self.current_user.id == user_id:
            self.response_error(
                HTTPStatus.FORBIDDEN, reason="You cannot delete your own account"
            )
            return

        try:
            await self.run_in_executor(self._webserver.auth.delete_user, user_id)
        except UserDoesNotExistError as error:
            self.response_error(HTTPStatus.NOT_FOUND, reason=str(error))
            return
        except LastAdminUserError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, reason=str(error))
            return

        await self.response_success()

    async def auth_login(self) -> None:
        """Login."""
        try:
            user = await self.run_in_executor(
                self._webserver.auth.validate_user,
                self.json_body["username"],
                self.json_body["password"],
            )
        except AuthenticationFailed:
            self.response_error(
                HTTPStatus.UNAUTHORIZED, reason="Invalid username or password"
            )
            return

        refresh_token = await self.run_in_executor(
            self._webserver.auth.generate_refresh_token,
            user.id,
            self.json_body["client_id"],
            "normal",
        )
        access_token = await self.run_in_executor(
            self._webserver.auth.generate_access_token,
            refresh_token,
            self.request.remote_ip,
        )

        self.set_cookies(refresh_token, access_token, user, new_session=True)

        await self.response_success(
            response=token_response(
                refresh_token,
                access_token,
            ),
        )

    async def auth_logout(self) -> None:
        """Logout."""
        refresh_token_cookie = self.get_secure_cookie("refresh_token")
        if refresh_token_cookie is not None:
            refresh_token = await self.run_in_executor(
                self._webserver.auth.get_refresh_token_from_token,
                refresh_token_cookie.decode(),
            )
            if refresh_token is not None:
                await self.run_in_executor(
                    self._webserver.auth.delete_refresh_token, refresh_token
                )

        self.clear_all_cookies()
        await self.response_success()

    def _handle_refresh_token(
        self,
    ) -> tuple[Literal[HTTPStatus.BAD_REQUEST], str] | tuple[
        Literal[HTTPStatus.OK], dict[str, Any]
    ]:
        """Handle refresh token."""
        refresh_token_cookie = self.get_secure_cookie("refresh_token")
        if refresh_token_cookie is None:
            return HTTPStatus.BAD_REQUEST, "Invalid refresh token"

        refresh_token = self._webserver.auth.get_refresh_token_from_token(
            refresh_token_cookie.decode()
        )

        if refresh_token is None:
            return HTTPStatus.BAD_REQUEST, "Invalid grant"

        if refresh_token.client_id != self.json_body["client_id"]:
            return HTTPStatus.BAD_REQUEST, "Invalid client_id"

        user = self._webserver.auth.get_user(refresh_token.user_id)
        if user is None:
            return HTTPStatus.BAD_REQUEST, "Invalid user"

        access_token = self._webserver.auth.generate_access_token(
            refresh_token, self.request.remote_ip
        )

        self.set_cookies(refresh_token, access_token, user, new_session=False)

        return (
            HTTPStatus.OK,
            token_response(
                refresh_token,
                access_token,
            ),
        )

    async def auth_token(self) -> None:
        """Handle token request."""
        if self.json_body["grant_type"] == "refresh_token":
            status, response = await self.run_in_executor(self._handle_refresh_token)
            if status == HTTPStatus.OK:
                await self.response_success(response=response)
                return
            self.clear_all_cookies()
            # Mypy doesn't understand that status is HTTPStatus.BAD_REQUEST here
            self.response_error(status, response)  # type: ignore[arg-type]
            return

        self.clear_all_cookies()
        self.response_error(
            HTTPStatus.BAD_REQUEST,
            reason="Invalid grant_type",
        )

    async def auth_users(self) -> None:
        """Get all users."""
        users = await self.run_in_executor(self._webserver.auth.get_users)
        response = {}
        response["users"] = list(users.values())
        await self.response_success(response=response)

    async def auth_admin_change_password(self, user_id: str) -> None:
        """Change the password of a user as an admin."""
        if self.current_user and self.current_user.role != Role.ADMIN:
            self.response_error(
                HTTPStatus.FORBIDDEN,
                reason="You are not authorized to change this password",
            )
            return

        try:
            await self.run_in_executor(
                self._webserver.auth.change_password,
                user_id,
                self.json_body["new_password"],
            )
        except UserDoesNotExistError as error:
            self.response_error(HTTPStatus.NOT_FOUND, reason=str(error))
            return

        await self.response_success()

    async def auth_update_user(self, user_id: str) -> None:
        """Update user details."""
        try:
            await self.run_in_executor(
                self._webserver.auth.update_user,
                user_id,
                self.json_body["name"],
                self.json_body["username"],
                Role(self.json_body["role"]),
            )
        except UserDoesNotExistError as error:
            self.response_error(HTTPStatus.NOT_FOUND, reason=str(error))
            return
        except UserExistsError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, reason=str(error))
            return
        except LastAdminUserError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, reason=str(error))
            return
        except (ValueError, InvalidRoleError) as error:
            self.response_error(HTTPStatus.BAD_REQUEST, reason=str(error))
            return

        await self.response_success()
