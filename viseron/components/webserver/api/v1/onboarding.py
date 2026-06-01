"""Onboarding API Handlers."""

from __future__ import annotations

import logging
from http import HTTPStatus

import voluptuous as vol

from viseron.components.webserver.api.handlers import BaseAPIHandler, require_auth
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
            "rate_limit": "onboarding",
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

    @require_auth
    async def onboarding(self) -> None:
        """Onboard the first user."""
        onboarding_complete = await self.run_in_executor(self.auth.onboarding_complete)
        if self.auth.users or onboarding_complete:
            self.response_error(
                HTTPStatus.FORBIDDEN,
                reason="Onboarding has already been completed",
            )
            return

        user = await self.run_in_executor(
            self.auth.onboard_user,
            self.json_body["name"],
            self.json_body["username"],
            self.json_body["password"],
        )

        refresh_token = await self.run_in_executor(
            self.auth.generate_refresh_token,
            user.id,
            self.json_body["client_id"],
            "normal",
        )
        access_token = await self.run_in_executor(
            self.auth.generate_access_token,
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
