"""Test the profile API handler."""

import json

from tests.components.webserver.common import USER_ID, TestAppBaseAuth


class TestProfileAPIHandler(TestAppBaseAuth):
    """Test the profile API handler."""

    def test_get_profile_available_timezones(self) -> None:
        """Test getting available timezones."""
        response = self.fetch_with_auth(
            "/api/v1/profile/available_timezones",
            method="GET",
        )
        assert response.code == 200
        body = json.loads(response.body)
        assert "timezones" in body
        assert isinstance(body["timezones"], list)
        assert "UTC" in body["timezones"]
        assert "Europe/Stockholm" in body["timezones"]

    def test_put_profile_preferences(self) -> None:
        """Test updating user preferences."""
        new_timezone = "Europe/Stockholm"
        response = self.fetch_with_auth(
            "/api/v1/profile/preferences",
            method="PUT",
            body=json.dumps({"timezone": new_timezone}),
        )
        assert response.code == 200

        user = self.webserver.auth.get_user(USER_ID)
        assert user is not None
        assert user.preferences is not None
        assert user.preferences.timezone == new_timezone

    def test_put_profile_display_name(self) -> None:
        """Test updating user display name."""
        new_name = "New Display Name"
        response = self.fetch_with_auth(
            "/api/v1/profile/display_name",
            method="PUT",
            body=json.dumps({"name": new_name}),
        )
        assert response.code == 200

        # Verify that the display name was updated
        user = self.webserver.auth.get_user(USER_ID)
        assert user.name == new_name

    def test_put_profile_preferences_clear(self) -> None:
        """Test clearing user timezone preference by setting it to null."""
        self.fetch_with_auth(
            "/api/v1/profile/preferences",
            method="PUT",
            body=json.dumps({"timezone": "Europe/Stockholm"}),
        )

        response = self.fetch_with_auth(
            "/api/v1/profile/preferences",
            method="PUT",
            body=json.dumps({"timezone": None}),
        )
        assert response.code == 200

        user = self.webserver.auth.get_user(USER_ID)
        assert user is not None
        assert user.preferences is not None
        assert user.preferences.timezone is None

    def test_put_profile_preferences_invalid_timezone(self) -> None:
        """Test that an invalid timezone returns an error."""
        response = self.fetch_with_auth(
            "/api/v1/profile/preferences",
            method="PUT",
            body=json.dumps({"timezone": "Invalid/Timezone"}),
        )
        assert response.code == 400
        body = json.loads(response.body)
        assert "Invalid timezone" in body["error"]

    def test_put_profile_preferences_unauthenticated(self) -> None:
        """Test that unauthenticated requests to preferences return 401."""
        response = self.fetch(
            "/api/v1/profile/preferences",
            method="PUT",
            body=json.dumps({"timezone": "UTC"}),
        )
        assert response.code == 401

    def test_put_profile_display_name_empty(self) -> None:
        """Test updating display name with an empty value returns 400."""
        response = self.fetch_with_auth(
            "/api/v1/profile/display_name",
            method="PUT",
            body=json.dumps({"name": "   "}),
        )
        assert response.code == 400
        assert json.loads(response.body) == {
            "error": "Name cannot be empty",
            "status": 400,
        }

    def test_put_profile_display_name_unauthenticated(self) -> None:
        """Test updating display name without auth returns 401."""
        response = self.fetch(
            "/api/v1/profile/display_name",
            method="PUT",
            body=json.dumps({"name": "New Name"}),
        )
        assert response.code == 401
