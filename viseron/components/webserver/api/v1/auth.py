"""Auth API Handlers."""
from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any, Literal

import voluptuous as vol

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import (
    AuthenticationFailed,
    Group,
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
            "path_pattern": r"/auth/create",
            "supported_methods": ["POST"],
            "method": "auth_create",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Required("group"): vol.In([e.value for e in Group]),
                }
            ),
        },
        {
            "path_pattern": r"/auth/user/(?P<user_id>[A-Za-z0-9_]+)",
            "supported_methods": ["GET"],
            "method": "auth_user",
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
    ]

    def auth_enabled(self):
        """Return if auth is enabled."""
        response = {
            "enabled": bool(self._webserver.auth) if self._webserver.auth else False,
            "onboarding_complete": self._webserver.auth.onboarding_complete
            if self._webserver.auth
            else False,
        }
        self.response_success(response=response)

    def auth_create(self):
        """Create a new user."""
        try:
            self._webserver.auth.add_user(
                self.json_body["name"].strip(),
                self.json_body["username"].strip().casefold(),
                self.json_body["password"],
                Group(self.json_body["group"]),
            )
        except UserExistsError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, reason=str(error))
            return
        self.response_success()

    def auth_user(self, user_id: str):
        """Get a user.

        Returns 200 OK with user data if user exists.
        """
        user = self._webserver.auth.get_user(user_id)
        if user is None:
            self.response_error(HTTPStatus.NOT_FOUND, reason="User not found")
            return
        self.response_success(
            response={
                "name": user.name,
                "username": user.username,
                "group": user.group.value,
            }
        )

    def auth_login(self):
        """Login."""
        try:
            user = self._webserver.auth.validate_user(
                self.json_body["username"], self.json_body["password"]
            )
        except AuthenticationFailed:
            self.response_error(
                HTTPStatus.UNAUTHORIZED, reason="Invalid username or password"
            )
            return

        refresh_token = self._webserver.auth.generate_refresh_token(
            user.id,
            self.json_body["client_id"],
            "normal",
        )
        access_token = self._webserver.auth.generate_access_token(
            refresh_token, self.request.remote_ip
        )

        self.set_cookies(refresh_token, access_token, user, new_session=True)

        self.response_success(
            response=token_response(
                refresh_token,
                access_token,
            ),
        )

    def auth_logout(self):
        """Logout."""
        refresh_token_cookie = self.get_secure_cookie("refresh_token")
        if refresh_token_cookie is None:
            self.response_error(HTTPStatus.BAD_REQUEST, reason="Invalid refresh token")
            return

        refresh_token = self._webserver.auth.get_refresh_token_from_token(
            refresh_token_cookie.decode()
        )
        if refresh_token is None:
            self.response_error(HTTPStatus.BAD_REQUEST, reason="Invalid refresh token")
            return

        self._webserver.auth.delete_refresh_token(refresh_token)
        self.clear_all_cookies()
        self.response_success()

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

    def auth_token(self):
        """Handle token request."""
        if self.json_body["grant_type"] == "refresh_token":
            status, response = self._handle_refresh_token()
            if status == HTTPStatus.OK:
                self.response_success(response=response)
                return
            self.response_error(status, response)
            return

        self.response_error(
            HTTPStatus.BAD_REQUEST,
            reason="Invalid grant_type",
        )
