"""Test the profile API handler."""

import json
import time

from viseron.components.webserver.auth import MAX_ACCESS_TOKENS_PER_USER

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
        response = self.fetch_with_auth(
            "/api/v1/profile/preferences",
            method="PUT",
            body=json.dumps(
                {
                    "timezone": "Europe/Stockholm",
                    "date_format": "DD/MM/YYYY",
                    "time_format": "12h",
                }
            ),
        )
        assert response.code == 200

        user = self.webserver.auth.get_user(USER_ID)
        assert user is not None
        assert user.preferences is not None
        assert user.preferences.timezone == "Europe/Stockholm"
        assert user.preferences.date_format == "DD/MM/YYYY"
        assert user.preferences.time_format == "12h"

    def test_put_profile_preferences_clear(self) -> None:
        """Test clearing preferences by setting values to null."""
        self.fetch_with_auth(
            "/api/v1/profile/preferences",
            method="PUT",
            body=json.dumps(
                {
                    "timezone": "Europe/Stockholm",
                    "date_format": "DD.MM.YYYY",
                    "time_format": "24h",
                }
            ),
        )

        response = self.fetch_with_auth(
            "/api/v1/profile/preferences",
            method="PUT",
            body=json.dumps(
                {
                    "timezone": None,
                    "date_format": None,
                    "time_format": None,
                }
            ),
        )
        assert response.code == 200

        user = self.webserver.auth.get_user(USER_ID)
        assert user is not None
        assert user.preferences is not None
        assert user.preferences.timezone is None
        assert user.preferences.date_format is None
        assert user.preferences.time_format is None

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

    def test_put_profile_preferences_invalid_date_format(self) -> None:
        """Test that an invalid date format returns an error."""
        response = self.fetch_with_auth(
            "/api/v1/profile/preferences",
            method="PUT",
            body=json.dumps(
                {
                    "timezone": None,
                    "date_format": "INVALID",
                }
            ),
        )
        assert response.code == 400
        body = json.loads(response.body)
        assert "Invalid date format" in body["error"]

    def test_put_profile_preferences_invalid_time_format(self) -> None:
        """Test that an invalid time format returns an error."""
        response = self.fetch_with_auth(
            "/api/v1/profile/preferences",
            method="PUT",
            body=json.dumps(
                {
                    "timezone": None,
                    "time_format": "INVALID",
                }
            ),
        )
        assert response.code == 400
        body = json.loads(response.body)
        assert "Invalid time format" in body["error"]

    def test_put_profile_preferences_unauthenticated(self) -> None:
        """Test that unauthenticated requests to preferences return 401."""
        response = self.fetch(
            "/api/v1/profile/preferences",
            method="PUT",
            body=json.dumps({"timezone": "UTC"}),
        )
        assert response.code == 401

    def test_put_profile_display_name(self) -> None:
        """Test updating user display name."""
        response = self.fetch_with_auth(
            "/api/v1/profile/display_name",
            method="PUT",
            body=json.dumps({"name": "New Display Name"}),
        )
        assert response.code == 200

        user = self.webserver.auth.get_user(USER_ID)
        assert user.name == "New Display Name"

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


class TestProfileAccessTokens(TestAppBaseAuth):
    """Test the profile access token API."""

    def _create_pat(self, name: str = "Test Token", expires_at=None):
        """Create a PAT via the API and return the parsed response body."""
        body: dict = {"name": name}
        if expires_at is not None:
            body["expires_at"] = expires_at
        response = self.fetch_with_auth(
            "/api/v1/profile/access_tokens",
            method="POST",
            body=json.dumps(body),
        )
        return response, json.loads(response.body)

    def test_get_profile_access_tokens_empty(self) -> None:
        """Token list is empty when no tokens exist yet."""
        response = self.fetch_with_auth(
            "/api/v1/profile/access_tokens",
            method="GET",
        )
        assert response.code == 200
        body = json.loads(response.body)
        assert body == {"access_tokens": []}

    def test_post_profile_access_tokens(self) -> None:
        """Creating a token returns id, name, created_at and the raw token once."""
        response, body = self._create_pat("CI token")
        assert response.code == 201
        assert "token" in body
        assert body["token"].startswith("vpat_")
        assert body["name"] == "CI token"
        assert "id" in body
        assert "created_at" in body
        # Token hash must NOT be exposed
        assert "token_hash" not in body

    def test_post_profile_access_tokens_with_expiry(self) -> None:
        """Expiry timestamp is persisted and returned."""
        future = time.time() + 3600
        response, body = self._create_pat("Expiring", expires_at=future)
        assert response.code == 201
        assert abs(body["expires_at"] - future) < 1

    def test_post_profile_access_tokens_missing_name(self) -> None:
        """Missing name field returns 400."""
        response = self.fetch_with_auth(
            "/api/v1/profile/access_tokens",
            method="POST",
            body=json.dumps({}),
        )
        assert response.code == 400

    def test_post_profile_access_tokens_empty_name(self) -> None:
        """Whitespace-only name returns 400."""
        response = self.fetch_with_auth(
            "/api/v1/profile/access_tokens",
            method="POST",
            body=json.dumps({"name": "   "}),
        )
        assert response.code == 400

    def test_post_profile_access_tokens_limit(self) -> None:
        """Test that creating more than the maximum allowed tokens returns 429."""
        for i in range(MAX_ACCESS_TOKENS_PER_USER):
            resp, _ = self._create_pat(f"Token {i}")
            assert resp.code == 201

        response, _ = self._create_pat("One too many")
        assert response.code == 429

    def test_get_profile_access_tokens_lists_created(self) -> None:
        """Tokens appear in the list after creation without raw token value."""
        _resp, created = self._create_pat("List me")
        response = self.fetch_with_auth(
            "/api/v1/profile/access_tokens",
            method="GET",
        )
        assert response.code == 200
        body = json.loads(response.body)
        ids = [t["id"] for t in body["access_tokens"]]
        assert created["id"] in ids
        # Raw token must NOT appear in the list
        for token in body["access_tokens"]:
            assert "token" not in token
            assert "token_hash" not in token

    def test_delete_profile_access_token(self) -> None:
        """Deleting a token removes it from the list."""
        _resp, created = self._create_pat("To delete")
        token_id = created["id"]

        response = self.fetch_with_auth(
            f"/api/v1/profile/access_tokens/{token_id}",
            method="DELETE",
        )
        assert response.code == 200

        list_resp = self.fetch_with_auth("/api/v1/profile/access_tokens", method="GET")
        ids = [t["id"] for t in json.loads(list_resp.body)["access_tokens"]]
        assert token_id not in ids

    def test_delete_profile_access_token_not_found(self) -> None:
        """Deleting a non-existent token returns 404."""
        fake_id = "a" * 32
        response = self.fetch_with_auth(
            f"/api/v1/profile/access_tokens/{fake_id}",
            method="DELETE",
        )
        assert response.code == 404

    def test_pat_authentication(self) -> None:
        """A valid PAT authenticates API requests without browser cookies."""
        _resp, created = self._create_pat("API access")
        raw_token = created["token"]

        response = self.fetch_with_pat(
            "/api/v1/profile/access_tokens",
            raw_token,
        )
        assert response.code == 200

    def test_pat_authentication_invalid_token(self) -> None:
        """An invalid PAT is rejected with 401."""
        response = self.fetch_with_pat(
            "/api/v1/profile/access_tokens",
            "vpat_invalidtoken",
        )
        assert response.code == 401

    def test_pat_authentication_expired(self) -> None:
        """An expired PAT is rejected with 401."""
        past = time.time() - 1
        _resp, created = self._create_pat("Expired token", expires_at=past)
        raw_token = created["token"]

        # Reload auth store so the expiry is persisted
        response = self.fetch_with_pat(
            "/api/v1/profile/access_tokens",
            raw_token,
        )
        assert response.code == 401

    def test_pat_not_accepted_in_browser_flow(self) -> None:
        """A PAT in the Authorization header WITH browser cookies must fail.

        The browser flow (X-Requested-With: XMLHttpRequest) requires a JWT whose
        signature is bound to the session cookies.  Sending a raw PAT through that
        path must be rejected to prevent CSRF/session-confusion attacks.
        """
        _resp, created = self._create_pat("Browser bypass attempt")
        raw_token = created["token"]

        # Simulate a browser request by setting X-Requested-With. The server then
        # expects a split JWT (header.payload in Authorization, signature in cookie).
        # Sending a raw PAT instead must be rejected.
        response = self.fetch_with_auth(
            "/api/v1/profile/access_tokens",
            method="GET",
            headers={
                "Authorization": f"Bearer {raw_token}",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        assert response.code == 401

    def test_post_profile_revoke_all(self) -> None:
        """Revoke all clears all sessions and PATs for the current user."""
        # Create a PAT so there is something to revoke
        self._create_pat("To be revoked")

        response = self.fetch_with_auth(
            "/api/v1/profile/revoke_all",
            method="POST",
            body="",
        )
        assert response.code == 200

        # Verify all refresh tokens for this user are gone
        rts = [
            rt
            for rt in self.webserver.auth.refresh_tokens.values()
            if rt.user_id == USER_ID
        ]
        assert len(rts) == 0

        # Verify all PATs for this user are gone
        pats = self.webserver.auth.get_access_tokens_for_user(USER_ID)
        assert len(pats) == 0

    def test_post_profile_revoke_all_unauthenticated(self) -> None:
        """Unauthenticated revoke_all returns 401."""
        response = self.fetch(
            "/api/v1/profile/revoke_all",
            method="POST",
            body="",
        )
        assert response.code == 401
