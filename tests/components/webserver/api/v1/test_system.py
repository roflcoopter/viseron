"""Test the System API handler."""
from __future__ import annotations

import json
from unittest.mock import PropertyMock, patch

from viseron.components.webserver.auth import Role, User

from tests.components.webserver.common import TestAppBaseAuth


class TestSystemApiHandler(TestAppBaseAuth):
    """Test the SystemAPIHandler."""

    def test_get_dispatched_events_admin(self):
        """Test getting dispatched events as admin."""
        with patch(
            "viseron.Viseron.dispatched_events",
            new_callable=PropertyMock,
            return_value=["event1", "event2"],
        ):
            response = self.fetch_with_auth("/api/v1/system/dispatched_events")
            assert response.code == 200
            data = json.loads(response.body)
            assert data == {"events": ["event1", "event2"]}

    def test_get_dispatched_events_non_admin(self):
        """Test getting dispatched events as non-admin."""
        with patch(
            "viseron.components.webserver.request_handler.ViseronRequestHandler.current_user",  # pylint: disable=line-too-long
            new_callable=PropertyMock,
            return_value=User(
                name="Test",
                username="test",
                password="test",
                role=Role.READ,
            ),
        ), patch(
            "viseron.components.webserver.request_handler.ViseronRequestHandler.validate_access_token",  # pylint: disable=line-too-long
            return_value=True,
        ):
            response = self.fetch_with_auth("/api/v1/system/dispatched_events")
            assert response.code == 403
