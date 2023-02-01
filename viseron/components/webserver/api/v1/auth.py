"""Auth API Handlers."""
from __future__ import annotations

import logging
from http import HTTPStatus
from typing import TYPE_CHECKING, Literal

import voluptuous as vol

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import AuthenticationFailed, UserExistsError

if TYPE_CHECKING:
    from viseron.components.webserver.auth import User

LOGGER = logging.getLogger(__name__)


class AuthAPIHandler(BaseAPIHandler):
    """Handler for API calls related to authentication."""

    routes = [
        {
            "path_pattern": r"/auth/create",
            "supported_methods": ["POST"],
            "method": "auth_create",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Optional("group", default=None): vol.Maybe(
                        vol.Any("admin", "user")
                    ),
                }
            ),
        },
        {
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
            "requires_auth": False,
            "path_pattern": r"/auth/token",
            "supported_methods": ["POST"],
            "method": "auth_token",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("grant_type", msg="Invalid grant_type"): vol.All(
                        vol.In(["refresh_token"]), str
                    ),
                    vol.Required("refresh_token"): str,
                    vol.Required("client_id"): str,
                }
            ),
        },
    ]

    def auth_create(self):
        """Create a new user."""
        try:
            self._webserver.auth.add_user(
                self.json_body["name"].strip(),
                self.json_body["username"].strip().casefold(),
                self.json_body["password"],
                self.json_body["group"],
            )
        except UserExistsError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, reason=str(error))
            return
        self.response_success()

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

        refresh_token = self._webserver.auth.generate_refresh_token(
            user.id,
            self.json_body["client_id"],
            "normal",
        )
        access_token = self._webserver.auth.generate_access_token(
            refresh_token, self.request.remote_ip
        )
        cookie_token = self._webserver.auth.generate_access_token(
            refresh_token, self.request.remote_ip
        )
        self.clear_cookie("token")
        self.clear_cookie("user")
        self.set_secure_cookie(
            "token",
            cookie_token,
            httponly=True,
            samesite="Lax",
            secure=bool(self.request.protocol == "https"),
        )
        self.set_secure_cookie(
            "user",
            user.id,
            httponly=True,
            samesite="Lax",
            secure=bool(self.request.protocol == "https"),
        )
        self.response_success(
            response={
                "access_token": access_token,
                "token_type": "Bearer",
                "refresh_token": refresh_token.token,
                "expires_in": int(
                    refresh_token.access_token_expiration.total_seconds()
                ),
            }
        )

    def _handle_refresh_token(
        self,
    ) -> tuple[Literal[HTTPStatus.BAD_REQUEST], str, None, None] | tuple[
        Literal[HTTPStatus.FORBIDDEN], str, None, None
    ] | tuple[Literal[HTTPStatus.OK], dict, str, User]:
        """Handle refresh token."""
        refresh_token = self._webserver.auth.get_refresh_token_from_token(
            self.json_body["refresh_token"]
        )

        if refresh_token is None:
            return HTTPStatus.BAD_REQUEST, "Invalid grant", None, None

        if refresh_token.client_id != self.json_body["client_id"]:
            return HTTPStatus.BAD_REQUEST, "Invalid client_id", None, None

        user = self._webserver.auth.get_user(refresh_token.user_id)
        if user is None:
            return HTTPStatus.FORBIDDEN, "Invalid user", None, None

        access_token = self._webserver.auth.generate_access_token(
            refresh_token, self.request.remote_ip
        )
        cookie_token = self._webserver.auth.generate_access_token(
            refresh_token, self.request.remote_ip
        )

        return (
            HTTPStatus.OK,
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": int(
                    refresh_token.access_token_expiration.total_seconds()
                ),
            },
            cookie_token,
            user,
        )

    def auth_token(self):
        """Handle token request."""
        if self.json_body["grant_type"] == "refresh_token":
            status, response, cookie_token, user = self._handle_refresh_token()
            if status == HTTPStatus.OK:
                self.clear_cookie("token")
                self.clear_cookie("user")
                self.set_secure_cookie(
                    "token",
                    cookie_token,
                    httponly=True,
                    samesite="Lax",
                    secure=bool(self.request.protocol == "https"),
                )
                self.set_secure_cookie(
                    "user",
                    user.id,
                    httponly=True,
                    samesite="Lax",
                    secure=bool(self.request.protocol == "https"),
                )
                self.response_success(response=response)
                return
            self.response_error(status, response)
            return

        self.response_error(
            HTTPStatus.BAD_REQUEST,
            reason="Invalid grant_type",
        )
