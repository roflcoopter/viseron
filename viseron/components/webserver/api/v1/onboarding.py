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
            "path_pattern": r"/onboarding",
            "supported_methods": ["POST"],
            "method": "onboarding",
            "json_body_schema": vol.Schema(
                {
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

        self._webserver.auth.add_user(
            self.json_body["name"],
            self.json_body["username"],
            self.json_body["password"],
            "admin",
        )
        Path(onboarding_file).touch()
        self.response_success()
