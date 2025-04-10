"""Auth tests."""
from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

import pytest

from viseron.components.webserver.auth import (
    Auth,
    AuthenticationFailed,
    InvalidRoleError,
    LastAdminUserError,
    Role,
    UserDoesNotExistError,
    UserExistsError,
    token_response,
)

WEBSERVER_CONFIG: dict[str, Any] = {"auth": {"session_expiry": None}}


class TestAuth:
    """Auth tests."""

    def setup_method(self, vis):
        """Set up tests."""
        self.auth = Auth(vis, WEBSERVER_CONFIG)

    def teardown_method(self):
        """Teardown tests."""
        if os.path.exists(
            self.auth._auth_store.path  # pylint: disable=protected-access
        ):
            os.remove(self.auth._auth_store.path)  # pylint: disable=protected-access
        if os.path.exists(self.auth.onboarding_path()):
            os.remove(self.auth.onboarding_path())

    def test_add_user(self):
        """Test adding user."""
        user = self.auth.add_user("Test", "Test ", "test", Role.ADMIN)
        assert user.name == "Test"
        assert user.username == "test"
        assert user.role == Role.ADMIN
        assert user.enabled is True
        assert user.password != "test"

        assert user.id in self.auth.users
        assert (
            os.path.exists(
                self.auth._auth_store.path  # pylint: disable=protected-access
            )
            is True
        )

        user2 = self.auth.add_user("Test2", "Test2", "test", Role.WRITE)
        assert user2.role == Role.WRITE

    def test_onboard_user(self):
        """Test oboarding user."""
        assert self.auth.onboarding_complete() is False
        self.auth.onboard_user("Test", "Test ", "test")
        assert self.auth.onboarding_complete() is True

    def test_add_user_invalid_role(self):
        """Test adding user with invalid role."""
        with pytest.raises(InvalidRoleError):
            self.auth.add_user(
                "Test",
                "Test ",
                "test",
                "invalid",  # type: ignore[arg-type]
            )

    def test_add_user_duplicate_username(self):
        """Test adding user with duplicate username."""
        self.auth.add_user("Test", "test", "test", Role.ADMIN)
        with pytest.raises(UserExistsError):
            self.auth.add_user("Test", "test", "test", Role.ADMIN)

    def test_hash_password(self):
        """Test hashing password."""
        hashed = self.auth.hash_password("test")
        hashed2 = self.auth.hash_password("test")
        assert hashed != hashed2

    def test_validate_user(self):
        """Test validating user."""
        user_add = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        user_pw = self.auth.validate_user("test", "test")
        assert user_add == user_pw

    def test_validate_user_invalid_password(self):
        """Test validating user with invalid password."""
        self.auth.add_user("Test", "test", "test", Role.ADMIN)
        with pytest.raises(AuthenticationFailed):
            self.auth.validate_user("test", "invalid")

    def test_validate_user_missing_user(self):
        """Test validating user with missing username."""
        self.auth.add_user("Test", "test", "test", Role.ADMIN)
        with pytest.raises(AuthenticationFailed):
            self.auth.validate_user("missing", "invalid")

    def test_get_user(self):
        """Test getting user."""
        user_add = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        user_get = self.auth.get_user(user_add.id)
        assert user_add == user_get

    def test_get_user_by_username(self):
        """Test getting user."""
        user_add = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        user_get = self.auth.get_user_by_username("test")
        assert user_add == user_get

    def test_get_users(self):
        """Test getting all users."""
        user1 = self.auth.add_user("Test1", "test1", "test", Role.ADMIN)
        user2 = self.auth.add_user("Test2", "test2", "test", Role.WRITE)
        users = self.auth.get_users()
        assert len(users) == 2
        assert user1.id in users
        assert user2.id in users

    def test_delete_user(self):
        """Test deleting a user."""
        user = self.auth.add_user("Test", "test", "test", Role.WRITE)
        assert user.id in self.auth.users

        self.auth.delete_user(user.id)
        assert user.id not in self.auth.users

    def test_delete_user_nonexistent(self):
        """Test deleting a nonexistent user."""
        with pytest.raises(UserDoesNotExistError):
            self.auth.delete_user("nonexistent_id")

    def test_delete_last_admin_user(self):
        """Test deleting the last admin user."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        with pytest.raises(
            LastAdminUserError, match="Cannot delete the last admin user"
        ):
            self.auth.delete_user(user.id)

    def test_change_password(self):
        """Test changing a user's password."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        self.auth.change_password(user.id, "new_password")
        updated_user = self.auth.validate_user("test", "new_password")
        assert updated_user == user

    def test_change_password_nonexistent_user(self):
        """Test changing the password of a nonexistent user."""
        with pytest.raises(UserDoesNotExistError):
            self.auth.change_password("nonexistent_id", "new_password")

    def test_update_user(self):
        """Test updating a user's details."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        self.auth.update_user(
            user.id, "Updated Name", "updated_username", Role.ADMIN, None
        )
        updated_user = self.auth.get_user(user.id)
        assert updated_user is not None
        assert updated_user.id == user.id
        assert updated_user.name == "Updated Name"
        assert updated_user.username == "updated_username"
        assert updated_user.role == Role.ADMIN

    def test_update_user_last_admin(self):
        """Test updating the last admin user."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        with pytest.raises(
            LastAdminUserError, match="Cannot change the role of the last admin user"
        ):
            self.auth.update_user(
                user.id, "Updated Name", "updated_username", Role.WRITE, None
            )

    def test_update_user_nonexistent(self):
        """Test updating a nonexistent user."""
        with pytest.raises(UserDoesNotExistError):
            self.auth.update_user(
                "nonexistent_id", "Updated Name", "updated_username", Role.WRITE, None
            )

    def test_update_user_duplicate_username(self):
        """Test updating a user with a duplicate username."""
        self.auth.add_user("Test1", "test1", "test", Role.ADMIN)
        user2 = self.auth.add_user("Test2", "test2", "test", Role.WRITE)
        with pytest.raises(UserExistsError, match="Username test1 is already taken"):
            self.auth.update_user(user2.id, "Updated Name", "test1", Role.WRITE, None)

    def test_update_user_invalid_role(self):
        """Test updating a user with an invalid role."""
        self.auth.add_user("Test", "test", "test", Role.ADMIN)
        user2 = self.auth.add_user("Test2", "test2", "test2", Role.WRITE)
        with pytest.raises(InvalidRoleError, match="Invalid role invalid"):
            self.auth.update_user(
                user2.id,
                "Updated Name",
                "updated_username",
                "invalid",  # type: ignore[arg-type]
                None,
            )

    def test_generate_refresh_token(self):
        """Test generating refresh token."""
        refresh_token = self.auth.generate_refresh_token(
            "test", "test_client", "normal", timedelta(seconds=3600)
        )
        assert refresh_token.user_id == "test"
        assert refresh_token.client_id == "test_client"
        assert refresh_token.access_token_type == "normal"
        assert refresh_token.access_token_expiration.total_seconds() == 3600
        assert refresh_token.used_at is None
        assert refresh_token.used_by is None
        assert refresh_token.id in self.auth.refresh_tokens

    def test_get_refresh_token(self):
        """Test getting refresh token."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        refresh_token_get = self.auth.get_refresh_token(refresh_token.id)
        assert refresh_token == refresh_token_get

    def test_get_refresh_token_from_token(self):
        """Test getting refresh token from token."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        refresh_token_get = self.auth.get_refresh_token_from_token(refresh_token.token)
        assert refresh_token == refresh_token_get

    def test_delete_refresh_token(self):
        """Test deleting refresh token."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        refresh_token_get = self.auth.get_refresh_token_from_token(refresh_token.token)
        assert refresh_token == refresh_token_get

        self.auth.delete_refresh_token(refresh_token)
        assert self.auth.get_refresh_token_from_token(refresh_token.token) is None

    def test_get_refresh_token_from_token_invalid_token(self):
        """Test getting refresh token from invalid token."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        refresh_token_get = self.auth.get_refresh_token_from_token("invalid")
        assert refresh_token_get is None

    def test_generate_access_token(self):
        """Test generating access token."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        self.auth.generate_access_token(refresh_token, "test_host")

    def test_validate_access_token(self):
        """Test validating access token."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        access_token = self.auth.generate_access_token(refresh_token, "test_host")
        assert self.auth.validate_access_token(access_token) == refresh_token

    def test_validate_access_token_expired(self):
        """Test validating access token expired."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=-10)
        )
        access_token = self.auth.generate_access_token(refresh_token, "test_host")
        assert self.auth.validate_access_token(access_token) is None

    def test_validating_access_token_invalid_token(self):
        """Test validating access token invalid token."""
        assert self.auth.validate_access_token("invalid") is None

    def test_validate_access_token_disabled_user(self):
        """Test validating access token for disabled user."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN, enabled=False)
        assert user.enabled is False
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        access_token = self.auth.generate_access_token(refresh_token, "test_host")
        assert self.auth.validate_access_token(access_token) is None

    def test_validate_access_token_missing_refresh_token(self):
        """Test validating access token missing refresh token."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        access_token = self.auth.generate_access_token(refresh_token, "test_host")
        self.auth.refresh_tokens.pop(refresh_token.id)
        assert self.auth.validate_access_token(access_token) is None

    def test_load(self, vis):
        """Test loading storage."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        user2 = self.auth.add_user("Test2", "test2", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        refresh_token2 = self.auth.generate_refresh_token(
            user2.id, "test_client", "normal", timedelta(seconds=3600)
        )
        assert len(self.auth.users.values()) == 2
        assert len(self.auth.refresh_tokens.values()) == 2
        assert refresh_token.token != refresh_token2.token
        assert refresh_token.jwt_key != refresh_token2.jwt_key

        auth2 = Auth(vis, WEBSERVER_CONFIG)
        assert len(auth2.users.values()) == 2
        assert len(auth2.refresh_tokens.values()) == 2
        for user in auth2.users.values():
            assert user.username == self.auth.users[user.id].username
            assert user.name == self.auth.users[user.id].name
        for refresh_token in auth2.refresh_tokens.values():
            assert (
                refresh_token.token == self.auth.refresh_tokens[refresh_token.id].token
            )
            assert (
                refresh_token.client_id
                == self.auth.refresh_tokens[refresh_token.id].client_id
            )
            assert (
                refresh_token.user_id
                == self.auth.refresh_tokens[refresh_token.id].user_id
            )
            assert (
                refresh_token.access_token_type
                == self.auth.refresh_tokens[refresh_token.id].access_token_type
            )
            assert (
                refresh_token.access_token_expiration.total_seconds()
                == self.auth.refresh_tokens[
                    refresh_token.id
                ].access_token_expiration.total_seconds()
            )
            assert (
                refresh_token.created_at
                == self.auth.refresh_tokens[refresh_token.id].created_at
            )

    def test_session_expiry(self, vis):
        """Test session expiry."""
        assert self.auth.session_expiry is None
        config = WEBSERVER_CONFIG.copy()
        config["auth"]["session_expiry"] = {"days": 1}
        auth = Auth(vis, config)
        assert auth.session_expiry == timedelta(days=1)

    def test_token_response(self):
        """Test token response."""
        refresh_token = self.auth.generate_refresh_token(
            "test", "test_client", "normal", timedelta(seconds=3600)
        )
        access_token = self.auth.generate_access_token(refresh_token, "test_host")
        header, payload, _signature = access_token.split(".")

        response = token_response(refresh_token, access_token)
        assert response["header"] == header
        assert response["payload"] == payload
