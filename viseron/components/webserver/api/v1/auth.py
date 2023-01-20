"""Auth API Handlers."""
from __future__ import annotations

import logging

import voluptuous as vol

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import UserExistsError
from viseron.components.webserver.const import STATUS_ERROR_EXTERNAL

LOGGER = logging.getLogger(__name__)


class AuthAPIHandler(BaseAPIHandler):
    """Handler for API calls related to a camera."""

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
            self.response_error(STATUS_ERROR_EXTERNAL, reason=str(error))
            return
        self.response_success()
