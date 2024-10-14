"""Test the API module.

This is sort of a combination of unit and integration tests.
Mocking is only done when it is strictly necessary.
"""
import json
import os
from pathlib import Path
from unittest.mock import PropertyMock, patch

from tests.components.webserver.common import (
    CLIENT_ID,
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
                    "group": "admin",
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
                    "group": "admin",
                }
            ),
        )
        assert response.code == 400
        assert json.loads(response.body) == {
            "error": f"A user with username {USER_NAME} already exists",
            "status": 400,
        }

    def test_auth_create_invalid_group(self):
        """Test adding a user with an invalid group."""
        response = self.fetch_with_auth(
            "/api/v1/auth/create",
            method="POST",
            body=json.dumps(
                {
                    "name": "test2",
                    "username": "test2",
                    "password": "test2",
                    "group": "invalid",
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
            "group": "admin",
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
        assert self.webserver.auth.refresh_tokens == {}

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
