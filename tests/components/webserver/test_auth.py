"""Auth tests."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from filelock import FileLock

from viseron.components.webserver.auth import (
    MAX_ACCESS_TOKENS_PER_USER,
    REFRESH_TOKEN_REUSE_GRACE,
    AccessTokenLimitExceededError,
    AccessTokenNotFoundError,
    Auth,
    AuthenticationFailedError,
    InvalidRoleError,
    LastAdminUserError,
    RefreshToken,
    Role,
    SessionExpiredError,
    UserDoesNotExistError,
    UserExistsError,
    token_response,
)

if TYPE_CHECKING:
    from viseron import Viseron

    from tests.conftest import MockViseron

WEBSERVER_CONFIG: dict[str, Any] = {"auth": {"session_expiry": None}}


class TestAuth:
    """Auth tests."""

    def setup_method(self, vis: Viseron):
        """Set up tests."""
        self.auth = Auth(vis, WEBSERVER_CONFIG)
        self.auth_store_lock = FileLock(f"{self.auth._auth_store.path}.lock")
        self.onboarding_lock = FileLock(f"{self.auth.onboarding_path()}.lock")
        self.auth_store_lock.acquire()
        self.onboarding_lock.acquire()

    def teardown_method(self):
        """Teardown tests."""
        if os.path.exists(self.auth._auth_store.path):
            os.remove(self.auth._auth_store.path)
        if os.path.exists(self.auth.onboarding_path()):
            os.remove(self.auth.onboarding_path())
        self.auth_store_lock.release()
        self.onboarding_lock.release()

    def test_add_user(self):
        """Test adding user."""
        user = self.auth.add_user("Test", "Test ", "test", Role.ADMIN)
        assert user.name == "Test"
        assert user.username == "test"
        assert user.role == Role.ADMIN
        assert user.enabled is True
        assert user.password != "test"

        assert user.id in self.auth.users
        assert os.path.exists(self.auth._auth_store.path) is True

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
        with pytest.raises(AuthenticationFailedError):
            self.auth.validate_user("test", "invalid")

    def test_validate_user_missing_user(self):
        """Test validating user with missing username."""
        self.auth.add_user("Test", "test", "test", Role.ADMIN)
        with pytest.raises(AuthenticationFailedError):
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

    def test_change_password_revokes_all_sessions(self):
        """Changing the password must invalidate all sessions and PATs."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        rt = self.auth.generate_refresh_token(user.id, "client", "normal")
        _pat, raw = self.auth.create_access_token(user.id, "My PAT")

        assert rt.id in self.auth.refresh_tokens
        assert self.auth.validate_access_token_pat(raw) is not None

        self.auth.change_password(user.id, "new_password")

        # All credentials for that user are gone.
        assert rt.id not in self.auth.refresh_tokens
        assert self.auth.validate_access_token_pat(raw) is None
        assert self.auth.get_access_tokens_for_user(user.id) == []

    def test_change_password_does_not_revoke_other_users(self):
        """Changing one user's password must not affect another user's tokens."""
        user_a = self.auth.add_user("A", "a", "a", Role.ADMIN)
        user_b = self.auth.add_user("B", "b", "b", Role.WRITE)
        rt_b = self.auth.generate_refresh_token(user_b.id, "client", "normal")
        _b_pat, b_raw = self.auth.create_access_token(user_b.id, "B PAT")

        self.auth.change_password(user_a.id, "new_password")

        assert rt_b.id in self.auth.refresh_tokens
        assert self.auth.validate_access_token_pat(b_raw) is not None

    def test_delete_user_revokes_all_sessions(self):
        """Deleting a user must invalidate all their sessions and PATs."""
        # Need an admin to remain so the test user can be deleted.
        self.auth.add_user("Admin", "admin", "admin", Role.ADMIN)
        user = self.auth.add_user("Test", "test", "test", Role.WRITE)
        rt = self.auth.generate_refresh_token(user.id, "client", "normal")
        _pat, raw = self.auth.create_access_token(user.id, "My PAT")

        self.auth.delete_user(user.id)

        assert user.id not in self.auth.users
        assert rt.id not in self.auth.refresh_tokens
        assert self.auth.validate_access_token_pat(raw) is None

    def test_delete_user_does_not_revoke_other_users(self):
        """Deleting one user must not affect another user's tokens."""
        admin = self.auth.add_user("Admin", "admin", "admin", Role.ADMIN)
        user_b = self.auth.add_user("B", "b", "b", Role.WRITE)
        rt_b = self.auth.generate_refresh_token(user_b.id, "client", "normal")
        _b_pat, b_raw = self.auth.create_access_token(user_b.id, "B PAT")

        # Delete a third user that has no tokens, verify B's are intact.
        target = self.auth.add_user("Target", "target", "target", Role.WRITE)
        self.auth.delete_user(target.id)

        assert admin.id in self.auth.users
        assert rt_b.id in self.auth.refresh_tokens
        assert self.auth.validate_access_token_pat(b_raw) is not None

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

    def test_rotate_refresh_token_rejects_already_consumed_token(self):
        """Test rotating an already-consumed refresh token."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )

        rotated_token = self.auth.rotate_refresh_token(refresh_token)
        assert rotated_token is not None
        assert refresh_token.id not in self.auth.refresh_tokens
        assert rotated_token.id in self.auth.refresh_tokens

        token_count = len(self.auth.refresh_tokens)
        assert self.auth.rotate_refresh_token(refresh_token) is None
        assert len(self.auth.refresh_tokens) == token_count

    def test_rotate_refresh_token_issues_new_secrets(self):
        """Rotation issues a brand-new token with fresh secrets."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )

        rotated = self.auth.rotate_refresh_token(refresh_token)
        assert rotated is not None
        assert rotated.id != refresh_token.id
        assert rotated.token != refresh_token.token
        assert rotated.jwt_key != refresh_token.jwt_key
        assert rotated.static_asset_key != refresh_token.static_asset_key

    def test_rotate_refresh_token_preserves_session_metadata(self):
        """Rotation must not extend the absolute session window."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )

        rotated = self.auth.rotate_refresh_token(refresh_token)
        assert rotated is not None
        assert rotated.created_at == refresh_token.created_at
        assert rotated.session_expiration == refresh_token.session_expiration
        assert rotated.user_id == refresh_token.user_id
        assert rotated.client_id == refresh_token.client_id
        assert rotated.access_token_type == refresh_token.access_token_type
        assert rotated.access_token_expiration == refresh_token.access_token_expiration

    def test_rotate_refresh_token_replay_rejected(self):
        """A second rotation of the same token (replay) is rejected."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        # Snapshot the pre-rotation token to simulate a concurrent/leaked copy.
        old_id = refresh_token.id
        old_token = refresh_token.token

        first = self.auth.rotate_refresh_token(refresh_token)
        assert first is not None
        assert self.auth.is_recent_refresh_token_reuse(old_token, "test_client")
        assert not self.auth.is_recent_refresh_token_reuse(old_token, "other_client")

        # Replay attempt with the original token must fail and not add a token.
        replay = RefreshToken(
            user_id=refresh_token.user_id,
            client_id=refresh_token.client_id,
            session_expiration=refresh_token.session_expiration,
            access_token_type=refresh_token.access_token_type,
            access_token_expiration=refresh_token.access_token_expiration,
            created_at=refresh_token.created_at,
            id=old_id,
            token=old_token,
        )
        token_count = len(self.auth.refresh_tokens)
        assert self.auth.rotate_refresh_token(replay) is None
        assert len(self.auth.refresh_tokens) == token_count
        assert old_id not in self.auth.refresh_tokens

    def test_rotate_refresh_token_tampered_token_rejected(self):
        """Rotation rejects a token whose secret has been tampered with."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        tampered = RefreshToken(
            user_id=refresh_token.user_id,
            client_id=refresh_token.client_id,
            session_expiration=refresh_token.session_expiration,
            access_token_type=refresh_token.access_token_type,
            access_token_expiration=refresh_token.access_token_expiration,
            created_at=refresh_token.created_at,
            id=refresh_token.id,
            token="tampered",  # noqa: S106
        )
        assert self.auth.rotate_refresh_token(tampered) is None
        assert refresh_token.id in self.auth.refresh_tokens

    def test_validate_refresh_token_expired_session(self):
        """validate_refresh_token raises once the absolute window has passed."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        # Move the issue time far enough into the past that any reasonable
        # session_expiration (including the 3650-day infinite sentinel) is gone.
        refresh_token.created_at = time.time() - timedelta(days=3651).total_seconds()

        with pytest.raises(SessionExpiredError):
            self.auth.validate_refresh_token(refresh_token)

    def test_validate_refresh_token_within_session(self):
        """validate_refresh_token does not raise while still within the window."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        # Default config has session_expiry=None -> 3650 days, freshly created.
        self.auth.validate_refresh_token(refresh_token)

    def test_rotate_refresh_token_expired_session_revokes(self):
        """An expired session is revoked rather than rotated."""
        config: dict[str, Any] = {"auth": {"session_expiry": {"hours": 1}}}
        auth = Auth(self.auth._vis, config)

        user = auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        # Force the token to be older than the configured 1h session window.
        refresh_token.created_at = time.time() - timedelta(hours=2).total_seconds()
        auth.refresh_tokens[refresh_token.id].created_at = refresh_token.created_at

        assert auth.rotate_refresh_token(refresh_token) is None
        assert refresh_token.id not in auth.refresh_tokens

    def test_is_recent_refresh_token_reuse_unknown_token(self):
        """Unknown tokens are never reported as recently rotated."""
        assert (
            self.auth.is_recent_refresh_token_reuse("not-a-token", "test_client")
            is False
        )

    def test_is_recent_refresh_token_reuse_after_rotation(self):
        """Old token + matching client_id is reported as recent reuse."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        old_token = refresh_token.token

        rotated = self.auth.rotate_refresh_token(refresh_token)
        assert rotated is not None

        assert self.auth.is_recent_refresh_token_reuse(old_token, "test_client")
        assert not self.auth.is_recent_refresh_token_reuse(old_token, "other_client")

    def test_is_recent_refresh_token_reuse_after_grace_expires(self):
        """Grace window expires after REFRESH_TOKEN_REUSE_GRACE."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        old_token = refresh_token.token

        assert self.auth.rotate_refresh_token(refresh_token) is not None
        assert self.auth.is_recent_refresh_token_reuse(old_token, "test_client")

        # Advance the clock past the grace window.
        future = (
            datetime.now(timezone.utc)
            + REFRESH_TOKEN_REUSE_GRACE
            + timedelta(seconds=1)
        )
        with patch("viseron.components.webserver.auth.utcnow", return_value=future):
            assert not self.auth.is_recent_refresh_token_reuse(old_token, "test_client")

        # The expired entry is purged on lookup.
        token_hash = Auth._hash_refresh_token(old_token)
        assert token_hash not in self.auth._recent_refresh_token_rotations

    def test_is_recent_refresh_token_reuse_after_replacement_revoked(self):
        """When the replacement token is gone, the entry is orphaned and purged."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        old_token = refresh_token.token

        rotated = self.auth.rotate_refresh_token(refresh_token)
        assert rotated is not None

        # Revoke the replacement.
        self.auth.delete_refresh_token(rotated)

        assert not self.auth.is_recent_refresh_token_reuse(old_token, "test_client")
        token_hash = Auth._hash_refresh_token(old_token)
        assert token_hash not in self.auth._recent_refresh_token_rotations

    def test_rotate_refresh_token_records_recent_rotation(self):
        """rotate_refresh_token records grace metadata for the old token."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        refresh_token = self.auth.generate_refresh_token(
            user.id, "test_client", "normal", timedelta(seconds=3600)
        )
        old_token = refresh_token.token

        before = time.time()
        rotated = self.auth.rotate_refresh_token(refresh_token)
        after = time.time()
        assert rotated is not None

        token_hash = Auth._hash_refresh_token(old_token)
        rotation = self.auth._recent_refresh_token_rotations[token_hash]
        assert rotation.client_id == "test_client"
        assert rotation.replacement_id == rotated.id
        assert (
            before + REFRESH_TOKEN_REUSE_GRACE.total_seconds()
            <= rotation.expires_at
            <= after + REFRESH_TOKEN_REUSE_GRACE.total_seconds()
        )

    def test_rotate_refresh_token_purges_expired_entries_on_new_rotation(self):
        """A later rotation purges other entries whose grace already elapsed."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        first = self.auth.generate_refresh_token(
            user.id, "client_a", "normal", timedelta(seconds=3600)
        )
        old_first_token = first.token
        assert self.auth.rotate_refresh_token(first) is not None
        assert (
            Auth._hash_refresh_token(old_first_token)
            in self.auth._recent_refresh_token_rotations
        )

        # Advance past the grace window, then rotate a second, independent token.
        future = (
            datetime.now(timezone.utc)
            + REFRESH_TOKEN_REUSE_GRACE
            + timedelta(seconds=1)
        )
        second = self.auth.generate_refresh_token(
            user.id, "client_b", "normal", timedelta(seconds=3600)
        )
        old_second_token = second.token
        with patch("viseron.components.webserver.auth.utcnow", return_value=future):
            assert self.auth.rotate_refresh_token(second) is not None

        # First entry is purged; second remains.
        assert (
            Auth._hash_refresh_token(old_first_token)
            not in self.auth._recent_refresh_token_rotations
        )
        assert (
            Auth._hash_refresh_token(old_second_token)
            in self.auth._recent_refresh_token_rotations
        )

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

    def test_load(self, vis: MockViseron):
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

    def test_session_expiry(self, vis: MockViseron):
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


class TestAccessToken:
    """Tests for personal access token (PAT) management."""

    def setup_method(self, vis: Viseron):
        """Set up tests."""
        self.auth = Auth(vis, WEBSERVER_CONFIG)
        self.auth_store_lock = FileLock(f"{self.auth._auth_store.path}.lock")
        self.onboarding_lock = FileLock(f"{self.auth.onboarding_path()}.lock")
        self.auth_store_lock.acquire()
        self.onboarding_lock.acquire()

    def teardown_method(self):
        """Teardown tests."""
        if os.path.exists(self.auth._auth_store.path):
            os.remove(self.auth._auth_store.path)
        if os.path.exists(self.auth.onboarding_path()):
            os.remove(self.auth.onboarding_path())
        self.auth_store_lock.release()
        self.onboarding_lock.release()

    def test_create_access_token(self):
        """Token is returned raw once; only its hash is stored."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        pat, raw_token = self.auth.create_access_token(user.id, "My Token")

        assert raw_token.startswith("vpat_")
        assert pat.id in self.auth.access_tokens
        # Raw token must NOT be stored
        assert self.auth.access_tokens[pat.id].token_hash != raw_token
        # Hash round-trip: validate_access_token_pat must accept the raw token
        assert self.auth.validate_access_token_pat(raw_token) is not None

    def test_create_access_token_name_validation(self):
        """Empty or whitespace-only names are rejected."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        with pytest.raises(ValueError, match="cannot be empty"):
            self.auth.create_access_token(user.id, "")
        with pytest.raises(ValueError, match="cannot be empty"):
            self.auth.create_access_token(user.id, "   ")

    def test_create_access_token_name_too_long(self):
        """Names exceeding 100 characters are rejected."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        with pytest.raises(ValueError, match="cannot exceed 100"):
            self.auth.create_access_token(user.id, "x" * 101)

    def test_create_access_token_with_expiry(self):
        """Optional expiry is stored on the token."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)

        future = time.time() + 3600
        pat, _raw = self.auth.create_access_token(
            user.id, "Expiring", expires_at=future
        )
        assert pat.expires_at == future

    def test_create_access_token_limit(self):
        """Creating more than MAX_ACCESS_TOKENS_PER_USER raises an error."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        for i in range(MAX_ACCESS_TOKENS_PER_USER):
            self.auth.create_access_token(user.id, f"Token {i}")
        with pytest.raises(AccessTokenLimitExceededError):
            self.auth.create_access_token(user.id, "One too many")

    def test_get_access_tokens_for_user(self):
        """Only tokens for the requested user are returned."""
        user_a = self.auth.add_user("A", "a", "a", Role.ADMIN)
        user_b = self.auth.add_user("B", "b", "b", Role.WRITE)
        self.auth.create_access_token(user_a.id, "A token 1")
        self.auth.create_access_token(user_a.id, "A token 2")
        self.auth.create_access_token(user_b.id, "B token 1")

        tokens_a = self.auth.get_access_tokens_for_user(user_a.id)
        tokens_b = self.auth.get_access_tokens_for_user(user_b.id)
        assert len(tokens_a) == 2
        assert len(tokens_b) == 1

    def test_delete_access_token(self):
        """Deleting a token removes it from the store."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        pat, _raw = self.auth.create_access_token(user.id, "To delete")
        self.auth.delete_access_token(pat.id, user.id)
        assert pat.id not in self.auth.access_tokens

    def test_delete_access_token_not_found(self):
        """Deleting a non-existent token raises AccessTokenNotFoundError."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        with pytest.raises(AccessTokenNotFoundError):
            self.auth.delete_access_token("nonexistent_id", user.id)

    def test_delete_access_token_wrong_user(self):
        """Deleting another user's token raises AccessTokenNotFoundError."""
        user_a = self.auth.add_user("A", "a", "a", Role.ADMIN)
        user_b = self.auth.add_user("B", "b", "b", Role.WRITE)
        pat, _raw = self.auth.create_access_token(user_a.id, "A token")
        with pytest.raises(AccessTokenNotFoundError):
            self.auth.delete_access_token(pat.id, user_b.id)

    def test_validate_access_token_pat(self):
        """A valid raw token returns the corresponding AccessToken."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        pat, raw_token = self.auth.create_access_token(user.id, "Valid")
        found = self.auth.validate_access_token_pat(raw_token)
        assert found is not None
        assert found.id == pat.id

    def test_validate_access_token_pat_invalid_token(self):
        """An unrecognised raw token returns None."""
        self.auth.add_user("Test", "test", "test", Role.ADMIN)
        assert self.auth.validate_access_token_pat("vpat_notavalidtoken") is None

    def test_validate_access_token_pat_expired(self):
        """An expired PAT is rejected even if the hash matches."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        past = time.time() - 1
        _pat, raw_token = self.auth.create_access_token(
            user.id, "Expired", expires_at=past
        )
        assert self.auth.validate_access_token_pat(raw_token) is None

    def test_access_token_load_save_round_trip(self, vis: MockViseron):
        """Test that PATs survive a save-and-reload cycle."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        _pat, raw_token = self.auth.create_access_token(user.id, "Persistent")

        auth2 = Auth(vis, WEBSERVER_CONFIG)
        found = auth2.validate_access_token_pat(raw_token)
        assert found is not None

    def test_update_pat_used(self):
        """After update_pat_used, last_used_at and last_used_by are set."""
        user = self.auth.add_user("Test", "test", "test", Role.ADMIN)
        pat, _raw = self.auth.create_access_token(user.id, "Used")
        assert pat.last_used_at is None
        self.auth.update_pat_used(pat, "192.168.1.1")
        assert pat.last_used_at is not None
        assert pat.last_used_by == "192.168.1.1"  # type: ignore[unreachable]

    def test_revoke_all_for_user(self):
        """revoke_all_for_user removes all sessions and PATs for the user only."""
        user_a = self.auth.add_user("A", "a", "a", Role.ADMIN)
        user_b = self.auth.add_user("B", "b", "b", Role.WRITE)

        # Give user_a a session and a PAT
        self.auth.generate_refresh_token(user_a.id, "client", "normal")
        self.auth.create_access_token(user_a.id, "A PAT")

        # Give user_b a session and a PAT (should survive)
        rt_b = self.auth.generate_refresh_token(user_b.id, "client", "normal")
        _b_pat, b_raw = self.auth.create_access_token(user_b.id, "B PAT")

        self.auth.revoke_all_for_user(user_a.id)

        # User A's tokens are gone
        rts_a = [
            rt for rt in self.auth.refresh_tokens.values() if rt.user_id == user_a.id
        ]
        pats_a = self.auth.get_access_tokens_for_user(user_a.id)
        assert len(rts_a) == 0
        assert len(pats_a) == 0

        # User B's tokens are unaffected
        assert rt_b.id in self.auth.refresh_tokens
        assert self.auth.validate_access_token_pat(b_raw) is not None
