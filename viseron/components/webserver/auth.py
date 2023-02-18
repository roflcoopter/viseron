"""Authentication."""
from __future__ import annotations

import base64
import enum
import hmac
import logging
import os
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Literal, cast

import bcrypt
import jwt

from viseron.components.webserver.const import (
    ACCESS_TOKEN_EXPIRATION,
    AUTH_STORAGE_KEY,
    CONFIG_AUTH,
    CONFIG_DAYS,
    CONFIG_HOURS,
    CONFIG_MINUTES,
    CONFIG_SESSION_EXPIRY,
    ONBOARDING_STORAGE_KEY,
)
from viseron.const import STORAGE_PATH
from viseron.exceptions import ViseronError
from viseron.helpers.storage import Storage

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)


class UserExistsError(ViseronError):
    """User already exists."""


class InvalidGroupError(ViseronError):
    """Invalid group specified."""


class AuthenticationFailed(ViseronError):
    """Authentication failed."""


@dataclass
class RefreshToken:
    """Refresh token.

    Used to get new access tokens.
    """

    user_id: str
    client_id: str
    access_token_type: Literal["normal"]
    access_token_expiration: timedelta = ACCESS_TOKEN_EXPIRATION
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    token: str = field(default_factory=lambda: secrets.token_hex(64))
    jwt_key: str = field(default_factory=lambda: secrets.token_hex(64))
    used_at: float | None = None
    used_by: str | None = None


class Group(enum.Enum):
    """Group enum."""

    ADMIN = "admin"
    USER = "user"


@dataclass
class User:
    """User."""

    name: str
    username: str
    password: str
    group: Group
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    enabled: bool = True


class Auth:
    """Users."""

    def __init__(self, vis: Viseron, config):
        self._vis = vis
        self._config = config
        self._users: dict[str, User] | None = None
        self._refresh_tokens: dict[str, RefreshToken] | None = None
        self._auth_store = Storage(vis, AUTH_STORAGE_KEY)
        self._data_lock = Lock()
        self._user_lock = Lock()

    @property
    def users(self) -> dict[str, User]:
        """Return users."""
        with self._data_lock:
            if self._users is None:
                LOGGER.debug("Loading users")
                self._load()
                assert self._users is not None
        return self._users

    @property
    def refresh_tokens(self) -> dict[str, RefreshToken]:
        """Return refresh tokens."""
        with self._data_lock:
            if self._refresh_tokens is None:
                LOGGER.debug("Loading refresh tokens")
                self._load()
                assert self._refresh_tokens is not None
        return self._refresh_tokens

    @property
    def session_expiry(self) -> timedelta | None:
        """Return session expiry."""
        if not self._config[CONFIG_AUTH][CONFIG_SESSION_EXPIRY]:
            return None

        return timedelta(
            days=self._config[CONFIG_AUTH][CONFIG_SESSION_EXPIRY].get(CONFIG_DAYS, 0),
            hours=self._config[CONFIG_AUTH][CONFIG_SESSION_EXPIRY].get(CONFIG_HOURS, 0),
            minutes=self._config[CONFIG_AUTH][CONFIG_SESSION_EXPIRY].get(
                CONFIG_MINUTES, 0
            ),
        )

    @property
    def onboarding_path(self) -> str:
        """Return onboarding path."""
        return os.path.join(STORAGE_PATH, ONBOARDING_STORAGE_KEY)

    @property
    def onboarding_complete(self) -> bool:
        """Return onboarding status."""
        if self.users or os.path.exists(self.onboarding_path):
            return True
        return False

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password."""
        return base64.b64encode(
            bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))
        ).decode()

    def add_user(
        self,
        name: str,
        username: str,
        password: str,
        group: Group | None = None,
        enabled: bool = True,
    ):
        """Add user."""
        LOGGER.debug(f"Adding user {username}")
        name = name.strip()
        username = username.strip().casefold()
        with self._user_lock:
            if self.get_user_by_username(username):
                raise UserExistsError(f"A user with username {username} already exists")

            if group is None:
                if not self.users:
                    LOGGER.debug("No users exist, setting group to admin")
                    group = Group.ADMIN
                else:
                    LOGGER.debug("No group specified, setting group to user")
                    group = Group.USER
            try:
                Group(group)
            except ValueError as error:
                raise InvalidGroupError(f"Invalid group {group}") from error
            user = User(
                name,
                username,
                self.hash_password(password),
                group,
                enabled=enabled,
            )
            self.users[user.id] = user
            self.save()
        return user

    def onboard_user(
        self,
        name: str,
        username: str,
        password: str,
    ):
        """Onboard the first user."""
        user = self.add_user(name, username, password, Group.ADMIN)
        Path(self.onboarding_path).touch()
        return user

    def validate_user(self, username: str, password: str) -> User:
        """Validate username and password.

        Raises:
            AuthenticationFailed: If authentication failed
        """
        username = username.strip().casefold()
        fakepw_hash = b"$2b$12$JkLmYgiPenMkcym29yHqReoa1dkONXqy6S2OBoU6FmjLShqDn/OuS"
        user = None

        # Loop over all users to avoid timing attacks.
        for _user in self.users.values():
            if _user.username == username:
                user = _user

        if user:
            if not bcrypt.checkpw(password.encode(), base64.b64decode(user.password)):
                raise AuthenticationFailed
            return user

        # Always check a fake password to avoid timing attacks.
        bcrypt.checkpw(b"fakepw", fakepw_hash)
        raise AuthenticationFailed

    def get_user(self, user_id: str) -> User | None:
        """Get user by id."""
        return self.users.get(user_id, None)

    def get_user_by_username(self, username: str) -> User | None:
        """Get user by username."""
        found = None
        for user in self.users.values():
            if user.username == username:
                found = user
        return found

    def _load(self):
        """Load users from storage."""
        LOGGER.debug("Loading data from auth store")
        data = self._auth_store.load()

        users: dict[str, User] = {}
        refresh_tokens: dict[str, RefreshToken] = {}

        for user in data.get("users", {}).values():
            users[user["id"]] = User(
                name=user["name"],
                username=user["username"],
                password=user["password"],
                group=user["group"],
                id=user["id"],
                enabled=user["enabled"],
            )

        for refresh_token in data.get("refresh_tokens", {}).values():
            refresh_tokens[refresh_token["id"]] = RefreshToken(
                user_id=refresh_token["user_id"],
                client_id=refresh_token["client_id"],
                access_token_type=refresh_token["access_token_type"],
                access_token_expiration=timedelta(
                    seconds=refresh_token["access_token_expiration"]
                ),
                created_at=refresh_token["created_at"],
                id=refresh_token["id"],
                token=refresh_token["token"],
                jwt_key=refresh_token["jwt_key"],
                used_at=refresh_token["used_at"],
                used_by=refresh_token["used_by"],
            )

        self._users = users
        self._refresh_tokens = refresh_tokens

    def save(self):
        """Save users to storage."""
        self._auth_store.save(
            {"users": self.users, "refresh_tokens": self.refresh_tokens}
        )

    def generate_refresh_token(
        self,
        user_id: str,
        client_id: str,
        access_token_type: Literal["normal"],
        access_token_expiration: timedelta = ACCESS_TOKEN_EXPIRATION,
    ):
        """Generate refresh token."""
        refresh_token = RefreshToken(
            user_id=user_id,
            client_id=client_id,
            access_token_type=access_token_type,
            access_token_expiration=access_token_expiration,
        )
        self.refresh_tokens[refresh_token.id] = refresh_token
        self.save()
        return refresh_token

    def get_refresh_token(self, refresh_token_id: str) -> RefreshToken | None:
        """Get refresh token."""
        return self.refresh_tokens.get(refresh_token_id, None)

    def get_refresh_token_from_token(self, token: str) -> RefreshToken | None:
        """Get refresh token from token."""
        found_token = None

        for refresh_token in self.refresh_tokens.values():
            if hmac.compare_digest(refresh_token.token, token):
                found_token = refresh_token

        return found_token

    def validate_refresh_token(self, refresh_token: RefreshToken):
        """Validate refresh token."""

    def generate_access_token(
        self, refresh_token: RefreshToken, remote_ip, expiry: timedelta | None = None
    ):
        """Generate access token using JWT."""
        self.validate_refresh_token(refresh_token)
        now = datetime.utcnow()
        refresh_token.used_at = now.timestamp()
        refresh_token.used_by = remote_ip
        self.save()
        return jwt.encode(
            {
                "iss": refresh_token.id,
                "iat": now,
                "exp": now + expiry
                if expiry
                else now + refresh_token.access_token_expiration,
            },
            refresh_token.jwt_key,
            algorithm="HS256",
        )

    def validate_access_token(self, access_token: str):
        """Validate access token."""
        try:
            unverif_claims = jwt.decode(
                access_token, algorithms=["HS256"], options={"verify_signature": False}
            )
        except jwt.InvalidTokenError:
            return None

        refresh_token = self.get_refresh_token(cast(str, unverif_claims.get("iss")))
        if refresh_token is None:
            jwt_key = ""
            issuer = ""
        else:
            jwt_key = refresh_token.jwt_key
            issuer = refresh_token.id

        try:
            jwt.decode(
                access_token, jwt_key, leeway=10, issuer=issuer, algorithms=["HS256"]
            )
        except jwt.InvalidTokenError:
            return None

        if refresh_token is None:
            return None

        user = self.get_user(refresh_token.user_id)
        if user is None or not user.enabled:
            return None

        return refresh_token
