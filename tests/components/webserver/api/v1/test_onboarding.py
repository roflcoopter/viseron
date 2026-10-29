"""Test the onboarding API handler."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from viseron.components.webserver.auth import Role

from tests.components.webserver.common import CLIENT_ID, TestAppBaseAuth

if TYPE_CHECKING:
    from tornado.httpclient import HTTPResponse


def _onboarding_body(username: str) -> str:
    return json.dumps(
        {
            "client_id": CLIENT_ID,
            "name": username,
            "username": username,
            "password": "password",
        }
    )


class TestOnboardingAPIHandler(TestAppBaseAuth):
    """Test the OnboardingAPIHandler."""

    def test_onboarding(self):
        """Test that the first user is onboarded as admin."""
        response = self.fetch(
            "/api/v1/onboarding", method="POST", body=_onboarding_body("admin")
        )
        assert response.code == 200
        users = list(self.webserver.auth.users.values())
        assert len(users) == 1
        assert users[0].username == "admin"
        assert users[0].role == Role.ADMIN
        assert self.webserver.auth.onboarding_complete() is True

    def test_onboarding_already_completed(self):
        """Test that a second onboarding with another username is rejected."""
        response = self.fetch(
            "/api/v1/onboarding", method="POST", body=_onboarding_body("admin")
        )
        assert response.code == 200

        response = self.fetch(
            "/api/v1/onboarding", method="POST", body=_onboarding_body("attacker")
        )
        assert response.code == 403
        assert len(self.webserver.auth.users) == 1

    def test_onboarding_concurrent(self):
        """Test that concurrent onboarding requests create exactly one admin."""
        usernames = ["admin", "attacker1", "attacker2", "attacker3"]

        async def onboard_concurrently() -> list[HTTPResponse]:
            return await asyncio.gather(
                *(
                    self.http_client.fetch(
                        self.get_url("/api/v1/onboarding"),
                        method="POST",
                        body=_onboarding_body(username),
                        raise_error=False,
                    )
                    for username in usernames
                )
            )

        responses = self.io_loop.run_sync(onboard_concurrently)

        assert sorted(response.code for response in responses) == [200, 403, 403, 403]
        assert len(self.webserver.auth.users) == 1
