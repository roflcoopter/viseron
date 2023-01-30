"""Onboarding API Handlers."""
from __future__ import annotations

import logging
import os
from http import HTTPStatus
from pathlib import Path

import voluptuous as vol

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.const import STORAGE_PATH

LOGGER = logging.getLogger(__name__)


class OnboardingAPIHandler(BaseAPIHandler):
    """Handler for API calls related to one-time onboarding."""

    routes = [
        {
            "requires_auth": False,
            "path_pattern": r"/onboarding",
            "supported_methods": ["POST"],
            "method": "onboarding",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("client_id"): str,
                    vol.Required("name"): str,
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                }
            ),
        },
    ]

    def onboarding(self):
        """Onboard the first user."""
        onboarding_file = os.path.join(STORAGE_PATH, "onboarding")
        if self._webserver.auth.users or os.path.exists(onboarding_file):
            self.response_error(
                HTTPStatus.FORBIDDEN,
                reason="Onboarding has already been completed",
            )
            return

        user = self._webserver.auth.add_user(
            self.json_body["name"],
            self.json_body["username"],
            self.json_body["password"],
            "admin",
        )
        Path(onboarding_file).touch()
        refresh_token = self._webserver.auth.generate_refresh_token(
            user.id, self.json_body["client_id"], "normal"
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
