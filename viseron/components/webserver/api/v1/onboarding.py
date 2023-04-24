"""Onboarding API Handlers."""
from __future__ import annotations

import logging
from http import HTTPStatus

import voluptuous as vol

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import token_response

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

    def onboarding(self) -> None:
        """Onboard the first user."""
        if self._webserver.auth.users or self._webserver.auth.onboarding_complete:
            self.response_error(
                HTTPStatus.FORBIDDEN,
                reason="Onboarding has already been completed",
            )
            return

        user = self._webserver.auth.onboard_user(
            self.json_body["name"],
            self.json_body["username"],
            self.json_body["password"],
        )

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
