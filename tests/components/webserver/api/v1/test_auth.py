"""Test the API module.

This is sort of a combination of unit and integration tests.
Mocking is only done when it is strictly necessary.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import PropertyMock, patch

from tornado.httpclient import HTTPResponse
from tornado.web import create_signed_value

from viseron.components.webserver.auth import (
    REFRESH_TOKEN_REUSE_GRACE,
    LastAdminUserError,
    Role,
    User,
    UserDoesNotExistError,
    UserExistsError,
)

from tests.components.webserver.common import (
    AUTH_STORAGE_DATA,
    CLIENT_ID,
    READ_REFRESH_TOKEN_ID,
    REFRESH_TOKEN_ID,
    USER_ID,
    USER_NAME,
    TestAppBaseAuth,
    TestAppBaseNoAuth,
)


class TestAuthAPIHandlerNoAuth(TestAppBaseNoAuth):
    """Test the AuthAPIHandler when auth is disabled."""

    def test_auth_enabled(self):
        """Test that the auth enabled endpoint returns the correct response."""
        response = self.fetch("/api/v1/auth/enabled")
        assert response.code == 200
        assert json.loads(response.body) == {
            "enabled": False,
            "onboarding_complete": False,
        }


class TestAuthAPIHandler(TestAppBaseAuth):
    """Test the AuthAPIHandler when auth is enabled."""

    def test_auth_enabled(self):
        """Test that the auth enabled endpoint returns the correct response."""
        response = self.fetch("/api/v1/auth/enabled")
        assert response.code == 200
        assert json.loads(response.body) == {
            "enabled": True,
            "onboarding_complete": False,
        }

        Path(self.webserver.auth.onboarding_path()).touch()
        response = self.fetch("/api/v1/auth/enabled")
        assert response.code == 200
        assert json.loads(response.body) == {
            "enabled": True,
            "onboarding_complete": True,
        }
        os.remove(self.webserver.auth.onboarding_path())

    def test_auth_create(self):
        """Test the auth create endpoint."""
        response = self.fetch_with_auth(
            "/api/v1/auth/create",
            method="POST",
            body=json.dumps(
                {
                    "name": "test",
                    "username": "testuser",
                    "password": "test",
                    "role": "admin",
                }
            ),
        )
        assert response.code == 200
        assert json.loads(response.body) == {
            "success": True,
        }

    def test_auth_create_exists(self):
        """Test adding a user that already exists."""
        response = self.fetch_with_auth(
            "/api/v1/auth/create",
            method="POST",
            body=json.dumps(
                {
                    "name": "test",
                    "username": USER_NAME,
                    "password": "test",
                    "role": "admin",
                }
            ),
        )
        assert response.code == 400
        assert json.loads(response.body) == {
            "error": f"A user with username {USER_NAME} already exists",
            "status": 400,
        }

    def test_auth_create_invalid_role(self):
        """Test adding a user with an invalid role."""
        response = self.fetch_with_auth(
            "/api/v1/auth/create",
            method="POST",
            body=json.dumps(
                {
                    "name": "test2",
                    "username": "test2",
                    "password": "test2",
                    "role": "invalid",
                }
            ),
        )
        assert response.code == 400
        body = json.loads(response.body)
        assert "Invalid body" in body["error"]
        assert body["status"] == 400

    def test_auth_user(self):
        """Test the auth user endpoint."""
        response = self.fetch_with_auth(
            f"/api/v1/auth/user/{USER_ID}",
            method="GET",
        )
        assert response.code == 200
        assert json.loads(response.body) == {
            "name": "Asd",
            "username": USER_NAME,
            "role": "admin",
            "preferences": None,
        }

    def test_auth_user_missing(self):
        """Test getting a user that doesn't exist."""
        response = self.fetch_with_auth(
            "/api/v1/auth/user/test",
            method="GET",
        )
        assert response.code == 404
        assert json.loads(response.body) == {
            "error": "User not found",
            "status": 404,
        }

    def test_auth_login(self):
        """Test the auth login endpoint."""
        response = self.fetch_with_auth(
            "/api/v1/auth/login",
            method="POST",
            body=json.dumps(
                {
                    "username": USER_NAME,
                    "password": "asd",
                    "client_id": "test",
                }
            ),
        )
        assert response.code == 200
        body = json.loads(response.body)
        assert "expiration" in body
        assert "expires_at" in body
        assert "header" in body
        assert "payload" in body
        assert "session_expires_at" in body

    def test_auth_login_invalid_username(self):
        """Test logging in with an invalid username."""
        response = self.fetch_with_auth(
            "/api/v1/auth/login",
            method="POST",
            body=json.dumps(
                {
                    "username": "invalid",
                    "password": "asd",
                    "client_id": "test",
                }
            ),
        )
        assert response.code == 401
        assert json.loads(response.body) == {
            "error": "Invalid username or password",
            "status": 401,
        }

    def test_auth_login_invalid_password(self):
        """Test logging in with an invalid password."""
        response = self.fetch_with_auth(
            "/api/v1/auth/login",
            method="POST",
            body=json.dumps(
                {
                    "username": USER_NAME,
                    "password": "invalid",
                    "client_id": "test",
                }
            ),
        )
        assert response.code == 401
        assert json.loads(response.body) == {
            "error": "Invalid username or password",
            "status": 401,
        }

    def test_auth_logout(self):
        """Test the auth logout endpoint."""
        response = self.fetch_with_auth(
            "/api/v1/auth/logout",
            method="POST",
            allow_nonstandard_methods=True,
        )
        assert response.code == 200
        assert json.loads(response.body) == {
            "success": True,
        }
        assert REFRESH_TOKEN_ID not in self.webserver.auth.refresh_tokens
        assert READ_REFRESH_TOKEN_ID in self.webserver.auth.refresh_tokens

    def test_auth_token(self):
        """Test the auth token endpoint."""
        response = self.fetch_with_auth(
            "/api/v1/auth/token",
            method="POST",
            body=json.dumps(
                {
                    "grant_type": "refresh_token",
                    "client_id": CLIENT_ID,
                }
            ),
        )
        assert response.code == 200
        body = json.loads(response.body)
        assert "expiration" in body
        assert "expires_at" in body
        assert "header" in body
        assert "payload" in body
        assert "session_expires_at" in body

    def test_auth_token_rotates_old_token(self):
        """A successful /auth/token revokes the old refresh token."""
        response = self.fetch_with_auth(
            "/api/v1/auth/token",
            method="POST",
            body=json.dumps(
                {
                    "grant_type": "refresh_token",
                    "client_id": CLIENT_ID,
                }
            ),
        )
        assert response.code == 200
        # Old token must be gone and replaced by a fresh one for the same user.
        assert REFRESH_TOKEN_ID not in self.webserver.auth.refresh_tokens
        new_tokens = [
            rt
            for rt in self.webserver.auth.refresh_tokens.values()
            if rt.user_id == USER_ID
        ]
        assert len(new_tokens) == 1
        assert new_tokens[0].token != "token"

    def test_auth_token_preserves_absolute_session_expiry(self):
        """Rotation must not extend the absolute session window."""
        self._seed_auth_store()
        original = self.webserver.auth.get_refresh_token(REFRESH_TOKEN_ID)
        assert original is not None
        original_session_expires_at = (
            original.created_at + original.session_expiration.total_seconds()
        )

        response = self.fetch_with_auth(
            "/api/v1/auth/token",
            method="POST",
            body=json.dumps(
                {
                    "grant_type": "refresh_token",
                    "client_id": CLIENT_ID,
                }
            ),
        )
        assert response.code == 200
        body = json.loads(response.body)
        # The rotated token's session_expires_at must equal the original's,
        # not be pushed forward by the refresh request.
        assert body["session_expires_at_timestamp"] == int(original_session_expires_at)

    def _replay_with_original_cookie(self, client_id: str = CLIENT_ID) -> HTTPResponse:
        """Replay /auth/token with the original (pre-rotation) refresh cookie."""
        refresh_token_cookie = create_signed_value(
            self._app.settings["cookie_secret"],
            "refresh_token",
            "token",
        ).decode()
        return self.fetch(
            "/api/v1/auth/token",
            method="POST",
            headers={"Cookie": f"refresh_token={refresh_token_cookie}"},
            body=json.dumps(
                {
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                }
            ),
        )

    def test_auth_token_replay_within_grace_does_not_clear_cookies(self):
        """A replay inside the reuse grace window must NOT clear cookies."""
        # Rotate once successfully
        response = self.fetch_with_auth(
            "/api/v1/auth/token",
            method="POST",
            body=json.dumps(
                {
                    "grant_type": "refresh_token",
                    "client_id": CLIENT_ID,
                }
            ),
        )
        assert response.code == 200

        replay = self._replay_with_original_cookie()
        assert replay.code == 400
        assert json.loads(replay.body) == {
            "error": "Invalid grant",
            "status": 400,
        }
        # Within the grace window the handler must NOT emit clearing cookies.
        assert not any(
            header.startswith("refresh_token=")
            for header in replay.headers.get_list("Set-Cookie")
        )

    def test_auth_token_replay_after_grace_clears_cookies(self):
        """A replay after the grace window has elapsed must clear cookies."""
        response = self.fetch_with_auth(
            "/api/v1/auth/token",
            method="POST",
            body=json.dumps(
                {
                    "grant_type": "refresh_token",
                    "client_id": CLIENT_ID,
                }
            ),
        )
        assert response.code == 200

        future = (
            datetime.now(timezone.utc)
            + REFRESH_TOKEN_REUSE_GRACE
            + timedelta(seconds=1)
        )
        with patch("viseron.components.webserver.auth.utcnow", return_value=future):
            replay = self._replay_with_original_cookie()

        assert replay.code == 400
        assert json.loads(replay.body) == {
            "error": "Invalid grant",
            "status": 400,
        }
        # The grace window is over -> the cookie must be cleared.
        assert any(
            header.startswith("refresh_token=")
            for header in replay.headers.get_list("Set-Cookie")
        )

    def test_auth_token_replay_wrong_client_id_clears_cookies(self):
        """A replay inside the grace window but with a different client_id clears."""
        response = self.fetch_with_auth(
            "/api/v1/auth/token",
            method="POST",
            body=json.dumps(
                {
                    "grant_type": "refresh_token",
                    "client_id": CLIENT_ID,
                }
            ),
        )
        assert response.code == 200

        replay = self._replay_with_original_cookie(client_id="some_other_client")
        assert replay.code == 400
        assert json.loads(replay.body) == {
            "error": "Invalid grant",
            "status": 400,
        }
        # client_id mismatch -> grace does NOT apply -> cookies must be cleared.
        assert any(
            header.startswith("refresh_token=")
            for header in replay.headers.get_list("Set-Cookie")
        )

    def test_auth_token_expired_session_rejected(self):
        """An expired session must not be rotatable."""
        self._seed_auth_store()
        token = self.webserver.auth.get_refresh_token(REFRESH_TOKEN_ID)
        assert token is not None
        # Force the seeded refresh token's session to have already elapsed.
        token.created_at = 0.0
        token.session_expiration = timedelta(seconds=1)

        response = self.fetch_with_auth(
            "/api/v1/auth/token",
            method="POST",
            body=json.dumps(
                {
                    "grant_type": "refresh_token",
                    "client_id": CLIENT_ID,
                }
            ),
        )
        assert response.code == 400
        assert json.loads(response.body) == {
            "error": "Invalid grant",
            "status": 400,
        }
        # The expired token must have been revoked.
        assert REFRESH_TOKEN_ID not in self.webserver.auth.refresh_tokens

    def _seed_auth_store(self) -> None:
        """Write the shared AUTH_STORAGE_DATA fixture and prime the loader.

        This is needed for tests that need to manipulate the refresh token's
        properties in ways that TestAppBaseAuth.fetch_with_auth doesn't allow,
        such as expiring the session or tampering with the token value.
        """
        os.makedirs(
            os.path.dirname(self.webserver.auth._auth_store.path),
            exist_ok=True,
        )
        with open(
            self.webserver.auth._auth_store.path,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(AUTH_STORAGE_DATA, file)
        self.webserver.auth._refresh_tokens = None
        self.webserver.auth._users = None
        # Touch the property to trigger _load().
        _ = self.webserver.auth.refresh_tokens

    def test_auth_token_invalid_grant(self):
        """Test getting a token with an invalid grant type."""
        response = self.fetch_with_auth(
            "/api/v1/auth/token",
            method="POST",
            body=json.dumps(
                {
                    "grant_type": "invalid",
                    "client_id": CLIENT_ID,
                }
            ),
        )
        assert response.code == 400
        body = json.loads(response.body)
        assert "Invalid body" in body["error"]
        assert body["status"] == 400

        # The json body schema guards against invalid grant types, so we
        # patch the json_body property to return an invalid grant type to
        # test the error handling in the handler
        with patch(
            "viseron.components.webserver.api.handlers.BaseAPIHandler.json_body",
            new_callable=PropertyMock,
            return_value={"grant_type": "invalid"},
        ):
            response = self.fetch_with_auth(
                "/api/v1/auth/token",
                method="POST",
                body=json.dumps(
                    {
                        "grant_type": "refresh_token",
                        "client_id": CLIENT_ID,
                    }
                ),
            )
            assert response.code == 400
            assert json.loads(response.body) == {
                "error": "Invalid grant_type",
                "status": 400,
            }

    def test_auth_token_invalid_client_id(self):
        """Test getting a token with an invalid client id."""
        response = self.fetch_with_auth(
            "/api/v1/auth/token",
            method="POST",
            body=json.dumps(
                {
                    "grant_type": "refresh_token",
                    "client_id": "invalid",
                }
            ),
        )
        assert response.code == 400
        assert json.loads(response.body) == {
            "error": "Invalid client_id",
            "status": 400,
        }

    def test_auth_token_invalid_refresh_token(self):
        """Test getting a token with an invalid refresh token."""
        with patch(
            "tornado.web.RequestHandler.get_secure_cookie",
            return_value=None,
        ):
            response = self.fetch_with_auth(
                "/api/v1/auth/token",
                method="POST",
                body=json.dumps(
                    {
                        "grant_type": "refresh_token",
                        "client_id": CLIENT_ID,
                    }
                ),
            )
        assert response.code == 400
        assert json.loads(response.body) == {
            "error": "Invalid refresh token",
            "status": 400,
        }

    def test_auth_token_invalid_refresh_token_user(self):
        """Test getting a token with an invalid refresh token user."""
        with patch(
            "viseron.components.webserver.auth.Auth.get_user",
            return_value=None,
        ):
            response = self.fetch_with_auth(
                "/api/v1/auth/token",
                method="POST",
                body=json.dumps(
                    {
                        "grant_type": "refresh_token",
                        "client_id": CLIENT_ID,
                    }
                ),
            )
        assert response.code == 400
        assert json.loads(response.body) == {
            "error": "Invalid user",
            "status": 400,
        }

    def test_auth_token_invalid_user(self):
        """Test getting a token with an invalid user."""
        with patch(
            "viseron.components.webserver.auth.Auth.get_user",
            return_value=None,
        ):
            response = self.fetch_with_auth(
                "/api/v1/auth/token",
                method="POST",
                body=json.dumps(
                    {
                        "grant_type": "refresh_token",
                        "client_id": CLIENT_ID,
                    }
                ),
            )
            assert response.code == 400
            assert json.loads(response.body) == {
                "error": "Invalid user",
                "status": 400,
            }

    def test_auth_delete(self):
        """Test deleting a user."""
        with patch("viseron.components.webserver.auth.Auth.delete_user"):
            response = self.fetch_with_auth(
                "/api/v1/auth/user/123456789",
                method="DELETE",
            )
            assert response.code == 200
            assert json.loads(response.body) == {"success": True}

    def test_auth_delete_self(self):
        """Test deleting your own user."""
        response = self.fetch_with_auth(
            f"/api/v1/auth/user/{USER_ID}",
            method="DELETE",
        )
        assert response.code == 403
        assert json.loads(response.body) == {
            "error": "You cannot delete your own account",
            "status": 403,
        }

    def test_auth_delete_nonexistent_user(self):
        """Test deleting a nonexistent user."""
        with patch(
            "viseron.components.webserver.auth.Auth.delete_user",
            side_effect=UserDoesNotExistError(
                "User with ID nonexistent_id does not exist"
            ),
        ):
            response = self.fetch_with_auth(
                "/api/v1/auth/user/nonexistent_id",
                method="DELETE",
            )
            assert response.code == 404
            assert json.loads(response.body) == {
                "error": "User with ID nonexistent_id does not exist",
                "status": 404,
            }

    def test_auth_delete_last_admin_user(self):
        """Test deleting the last admin user."""
        with (
            patch(
                "viseron.components.webserver.auth.Auth.delete_user",
                side_effect=LastAdminUserError("Cannot delete the last admin user"),
            ),
            patch(
                "viseron.components.webserver.request_handler.ViseronRequestHandler.current_user",  # pylint: disable=line-too-long
                new_callable=PropertyMock,
                return_value=User(
                    name="Test",
                    username="test",
                    password="test",
                    role=Role.ADMIN,
                ),
            ),
            patch(
                "viseron.components.webserver.request_handler.ViseronRequestHandler.validate_access_token",  # pylint: disable=line-too-long
                return_value=True,
            ),
        ):
            response = self.fetch_with_auth(
                f"/api/v1/auth/user/{USER_ID}",
                method="DELETE",
            )
            assert response.code == 400
            assert json.loads(response.body) == {
                "error": "Cannot delete the last admin user",
                "status": 400,
            }

    def test_auth_users(self):
        """Test retrieving all users."""
        response = self.fetch_with_auth("/api/v1/auth/users", method="GET")
        assert response.code == 200
        users = json.loads(response.body)["users"]
        assert len(users) == 2
        assert users[0]["id"] == USER_ID
        assert users[0]["username"] == USER_NAME

    def test_auth_admin_change_password(self):
        """Test changing a user's password as an admin."""
        with patch(
            "viseron.components.webserver.auth.Auth.change_password"
        ) as mock_change_password:
            mock_change_password.return_value = None
            response = self.fetch_with_auth(
                f"/api/v1/auth/user/{USER_ID}/admin_change_password",
                method="PUT",
                body=json.dumps({"new_password": "new_password"}),
            )
            assert response.code == 200
            assert json.loads(response.body) == {"success": True}

    def test_auth_admin_change_password_not_admin(self):
        """Test changing a user's password when not an admin."""
        with (
            patch(
                "viseron.components.webserver.request_handler.ViseronRequestHandler.current_user",  # pylint: disable=line-too-long
                new_callable=PropertyMock,
                return_value=User(
                    name="Test",
                    username="test",
                    password="test",
                    role=Role.READ,
                ),
            ),
            patch(
                "viseron.components.webserver.request_handler.ViseronRequestHandler.validate_access_token",  # pylint: disable=line-too-long
                return_value=True,
            ),
        ):
            response = self.fetch_with_auth(
                f"/api/v1/auth/user/{USER_ID}/admin_change_password",
                method="PUT",
                body=json.dumps({"new_password": "new_password"}),
            )
            assert response.code == 403
            assert json.loads(response.body) == {
                "error": "Insufficient permissions",
                "status": 403,
            }

    def test_auth_change_password_nonexistent_user(self):
        """Test changing the password of a nonexistent user."""
        with patch(
            "viseron.components.webserver.auth.Auth.change_password",
            side_effect=UserDoesNotExistError(
                "User with ID nonexistent_id does not exist"
            ),
        ):
            response = self.fetch_with_auth(
                "/api/v1/auth/user/nonexistent_id/admin_change_password",
                method="PUT",
                body=json.dumps({"new_password": "new_password"}),
            )
            assert response.code == 404
            assert json.loads(response.body) == {
                "error": "User with ID nonexistent_id does not exist",
                "status": 404,
            }

    def test_auth_update_user(self):
        """Test updating a user's details."""
        with patch(
            "viseron.components.webserver.auth.Auth.update_user"
        ) as mock_update_user:
            mock_update_user.return_value = None
            response = self.fetch_with_auth(
                f"/api/v1/auth/user/{USER_ID}",
                method="PUT",
                body=json.dumps(
                    {
                        "name": "Updated Name",
                        "username": "updated_username",
                        "role": "write",
                        "assigned_cameras": None,
                    }
                ),
            )
            assert response.code == 200
            assert json.loads(response.body) == {"success": True}

    def test_auth_update_user_nonexistent(self):
        """Test updating a nonexistent user."""
        with patch(
            "viseron.components.webserver.auth.Auth.update_user",
            side_effect=UserDoesNotExistError(
                "User with ID nonexistent_id does not exist"
            ),
        ):
            response = self.fetch_with_auth(
                "/api/v1/auth/user/nonexistent_id",
                method="PUT",
                body=json.dumps(
                    {
                        "name": "Updated Name",
                        "username": "updated_username",
                        "role": "write",
                        "assigned_cameras": None,
                    }
                ),
            )
            assert response.code == 404
            assert json.loads(response.body) == {
                "error": "User with ID nonexistent_id does not exist",
                "status": 404,
            }

    def test_auth_update_user_duplicate_username(self):
        """Test updating a user with a duplicate username."""
        with patch(
            "viseron.components.webserver.auth.Auth.update_user",
            side_effect=UserExistsError("Username test1 is already taken"),
        ):
            response = self.fetch_with_auth(
                f"/api/v1/auth/user/{USER_ID}",
                method="PUT",
                body=json.dumps(
                    {
                        "name": "Updated Name",
                        "username": "test1",
                        "role": "write",
                        "assigned_cameras": None,
                    }
                ),
            )
            assert response.code == 400
            assert json.loads(response.body) == {
                "error": "Username test1 is already taken",
                "status": 400,
            }

    def test_auth_update_user_invalid_role(self):
        """Test updating a user with an invalid role."""
        body = {
            "name": "Updated Name",
            "username": "updated_username",
            "role": "invalid",
            "assigned_cameras": None,
        }
        response = self.fetch_with_auth(
            "/api/v1/auth/user/123456789",
            method="PUT",
            body=json.dumps(body),
        )
        assert response.code == 400
        _body = json.loads(response.body)
        assert "Invalid body" in _body["error"]
