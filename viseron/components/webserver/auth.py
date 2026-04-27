"""Authentication."""

from __future__ import annotations

import base64
import datetime
import enum
import hashlib
import hmac
import logging
import os
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any, Literal, cast
from zoneinfo import available_timezones

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
from viseron.helpers import utcnow
from viseron.helpers.storage import Storage

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)


class UserExistsError(ViseronError):
    """User already exists."""


class InvalidRoleError(ViseronError):
    """Invalid role specified."""


class AuthenticationFailedError(ViseronError):
    """Authentication failed."""


class UserDoesNotExistError(ViseronError):
    """User does not exist."""


class LastAdminUserError(ViseronError):
    """Cannot delete the last admin user."""


class InvalidTimezoneError(ViseronError):
    """Invalid timezone specified."""


class InvalidDateFormatError(ViseronError):
    """Invalid date format specified."""


class InvalidTimeFormatError(ViseronError):
    """Invalid time format specified."""


class AccessTokenNotFoundError(ViseronError):
    """Access token not found."""


class AccessTokenLimitExceededError(ViseronError):
    """Access token limit exceeded."""


MAX_ACCESS_TOKENS_PER_USER = 20
MAX_TOKEN_NAME_LENGTH = 100
PAT_LAST_USED_SAVE_INTERVAL = datetime.timedelta(minutes=1)


VALID_DATE_FORMATS = [
    "YYYY-MM-DD",
    "MM/DD/YYYY",
    "DD/MM/YYYY",
    "DD.MM.YYYY",
    "MM-DD-YYYY",
    "DD-MM-YYYY",
]

VALID_TIME_FORMATS = [
    "12h",
    "24h",
]


@dataclass
class RefreshToken:
    """Refresh token.

    Used to get new access tokens.
    """

    user_id: str
    client_id: str
    session_expiration: datetime.timedelta
    access_token_type: Literal["normal"]
    access_token_expiration: datetime.timedelta = ACCESS_TOKEN_EXPIRATION
    created_at: float = field(default_factory=lambda: utcnow().timestamp())
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    token: str = field(default_factory=lambda: secrets.token_hex(64))
    jwt_key: str = field(default_factory=lambda: secrets.token_hex(64))
    static_asset_key: str = field(default_factory=lambda: secrets.token_hex(64))
    used_at: float | None = None
    used_by: str | None = None


@dataclass
class AccessToken:
    """Personal access token.

    Used to access the API from third-party clients.
    Only the SHA-256 hash of the raw token is ever stored.
    """

    user_id: str
    name: str
    token_hash: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = field(default_factory=lambda: utcnow().timestamp())
    expires_at: float | None = None
    last_used_at: float | None = None
    last_used_by: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Convert to dict, excluding the token_hash."""
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_used_at": self.last_used_at,
            "last_used_by": self.last_used_by,
        }


class Role(enum.Enum):
    """Role enum."""

    ADMIN = "admin"
    READ = "read"
    WRITE = "write"


@dataclass
class Preferences:
    """User preferences."""

    timezone: str | None = None
    date_format: str | None = None
    time_format: str | None = None

    def asdict(self) -> dict[str, Any]:
        """Convert preferences to dict."""
        return {
            "timezone": self.timezone,
            "date_format": self.date_format,
            "time_format": self.time_format,
        }


@dataclass
class User:
    """User."""

    name: str
    username: str
    password: str
    role: Role
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    enabled: bool = True
    assigned_cameras: list[str] | None = None
    preferences: Preferences | None = None

    def asdict(self) -> dict[str, Any]:
        """Convert user to dict."""
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "role": self.role.value,
            "assigned_cameras": self.assigned_cameras,
            "preferences": self.preferences,
        }


@dataclass
class TokenResponse:
    """Token response."""

    header: str
    payload: str
    expiration: int
    expires_at: datetime.datetime
    expires_at_timestamp: int
    session_expires_at: datetime.datetime
    session_expires_at_timestamp: int


def token_response(
    refresh_token: RefreshToken,
    access_token: str,
) -> dict[str, Any]:
    """Create token response."""
    header, payload, _signature = access_token.split(".")
    expires_at = utcnow() + refresh_token.access_token_expiration
    session_expires_at = datetime.datetime.fromtimestamp(
        refresh_token.created_at + refresh_token.session_expiration.total_seconds(),
        tz=datetime.timezone.utc,
    )
    return asdict(
        TokenResponse(
            header=header,
            payload=payload,
            expiration=int(refresh_token.access_token_expiration.total_seconds()),
            expires_at=expires_at,
            expires_at_timestamp=int(expires_at.timestamp()),
            session_expires_at=session_expires_at,
            session_expires_at_timestamp=int(session_expires_at.timestamp()),
        )
    )


class Auth:
    """Users."""

    def __init__(self, vis: Viseron, config: dict[str, Any]) -> None:
        self._vis = vis
        self._config = config
        self._users: dict[str, User] | None = None
        self._refresh_tokens: dict[str, RefreshToken] | None = None
        self._access_tokens: dict[str, AccessToken] | None = None
        self._pat_last_used_persisted_at: dict[str, float] = {}
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
                assert self._users is not None  # noqa: S101
        return self._users

    @property
    def refresh_tokens(self) -> dict[str, RefreshToken]:
        """Return refresh tokens."""
        with self._data_lock:
            if self._refresh_tokens is None:
                LOGGER.debug("Loading refresh tokens")
                self._load()
                assert self._refresh_tokens is not None  # noqa: S101
        return self._refresh_tokens

    @property
    def access_tokens(self) -> dict[str, AccessToken]:
        """Return personal access tokens."""
        with self._data_lock:
            if self._access_tokens is None:
                LOGGER.debug("Loading access tokens")
                self._load()
                assert self._access_tokens is not None  # noqa: S101
        return self._access_tokens

    @property
    def session_expiry(self) -> datetime.timedelta | None:
        """Return session expiry."""
        if not self._config[CONFIG_AUTH][CONFIG_SESSION_EXPIRY]:
            return None

        return datetime.timedelta(
            days=self._config[CONFIG_AUTH][CONFIG_SESSION_EXPIRY].get(CONFIG_DAYS, 0),
            hours=self._config[CONFIG_AUTH][CONFIG_SESSION_EXPIRY].get(CONFIG_HOURS, 0),
            minutes=self._config[CONFIG_AUTH][CONFIG_SESSION_EXPIRY].get(
                CONFIG_MINUTES, 0
            ),
        )

    def get_users(self) -> dict[str, User]:
        """Get all users."""
        return self.users

    def onboarding_path(self) -> str:
        """Return onboarding path."""
        return os.path.join(STORAGE_PATH, ONBOARDING_STORAGE_KEY)

    def onboarding_complete(self) -> bool:
        """Return onboarding status."""
        return bool(self.users or os.path.exists(self.onboarding_path()))

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
        role: Role,
        *,
        enabled: bool = True,
    ) -> User:
        """Add user."""
        LOGGER.debug(f"Adding user {username}")
        name = name.strip()
        username = username.strip().casefold()
        with self._user_lock:
            if self.get_user_by_username(username):
                raise UserExistsError(f"A user with username {username} already exists")

            if not isinstance(role, Role):
                raise InvalidRoleError(f"Invalid role {role}")

            user = User(
                name,
                username,
                self.hash_password(password),
                role,
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
    ) -> User:
        """Onboard the first user."""
        user = self.add_user(name, username, password, Role.ADMIN)
        Path(self.onboarding_path()).touch()
        return user

    def validate_user(self, username: str, password: str) -> User:
        """Validate username and password."""
        username = username.strip().casefold()
        fakepw_hash = b"$2b$12$JkLmYgiPenMkcym29yHqReoa1dkONXqy6S2OBoU6FmjLShqDn/OuS"
        user = None

        # Loop over all users to avoid timing attacks.
        for _user in self.users.values():
            if _user.username == username:
                user = _user

        if user:
            if not bcrypt.checkpw(password.encode(), base64.b64decode(user.password)):
                raise AuthenticationFailedError
            return user

        # Always check a fake password to avoid timing attacks.
        bcrypt.checkpw(b"fakepw", fakepw_hash)
        raise AuthenticationFailedError

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

    def delete_user(self, user_id: str) -> None:
        """Delete a user."""
        with self._user_lock:
            if user_id not in self.users:
                raise UserDoesNotExistError(f"User with ID {user_id} does not exist")

            # Prevent deletion of the last admin user
            user_to_delete = self.users[user_id]
            if user_to_delete.role == Role.ADMIN:
                admin_count = sum(
                    1 for user in self.users.values() if user.role == Role.ADMIN
                )
                if admin_count <= 1:
                    raise LastAdminUserError("Cannot delete the last admin user")

            LOGGER.debug(f"Deleting user {user_to_delete.username}")
            del self.users[user_id]
            self.save()

    def change_password(self, user_id: str, new_password: str) -> None:
        """Change the password of a user."""
        with self._user_lock:
            if user_id not in self.users:
                raise UserDoesNotExistError(f"User with ID {user_id} does not exist")

            user = self.users[user_id]
            user.password = self.hash_password(new_password)
            LOGGER.debug(f"Password changed for user {user.username}")
            self.save()

    def update_user(
        self,
        user_id: str,
        name: str,
        username: str,
        role: Role,
        assigned_cameras: list[str] | None,
    ) -> None:
        """Update user details."""
        with self._user_lock:
            if user_id not in self.users:
                raise UserDoesNotExistError(f"User with ID {user_id} does not exist")

            user = self.users[user_id]

            # Check if the new username is already taken by another user
            if (
                username.strip().casefold() != user.username
                and self.get_user_by_username(username.strip().casefold())
            ):
                raise UserExistsError(f"Username {username} is already taken")

            # Prevent role change of the last admin user
            if user.role == Role.ADMIN and role != Role.ADMIN:
                admin_count = sum(
                    1 for _user in self.users.values() if _user.role == Role.ADMIN
                )
                if admin_count <= 1:
                    raise LastAdminUserError(
                        "Cannot change the role of the last admin user"
                    )

            if not isinstance(role, Role):
                raise InvalidRoleError(f"Invalid role {role}")

            user.name = name.strip()
            user.username = username.strip().casefold()
            user.role = role
            user.assigned_cameras = assigned_cameras
            LOGGER.debug(f"Updated user {user.username}")
            self.save()

    def update_display_name(self, user_id: str, name: str) -> None:
        """Update the display name for a user."""
        trimmed_name = name.strip()
        if not trimmed_name:
            raise ValueError("Display name cannot be empty")

        with self._user_lock:
            if user_id not in self.users:
                raise UserDoesNotExistError(f"User with ID {user_id} does not exist")

            user = self.users[user_id]
            user.name = trimmed_name
            LOGGER.debug(f"Updated display name for user {user.username}")
            self.save()

    def update_preferences(
        self,
        user_id: str,
        preferences: Preferences,
    ) -> None:
        """Update user preferences."""
        with self._user_lock:
            if user_id not in self.users:
                raise UserDoesNotExistError(f"User with ID {user_id} does not exist")

            user = self.users[user_id]

            # Validate timezone if provided
            timezone = preferences.timezone
            if timezone is not None and timezone not in available_timezones():
                raise InvalidTimezoneError(f"Invalid timezone: {timezone}")

            # Validate date_format if provided
            date_format = preferences.date_format
            if date_format is not None and date_format not in VALID_DATE_FORMATS:
                raise InvalidDateFormatError(f"Invalid date format: {date_format}")

            # Validate time_format if provided
            time_format = preferences.time_format
            if time_format is not None and time_format not in VALID_TIME_FORMATS:
                raise InvalidTimeFormatError(f"Invalid time format: {time_format}")

            # Update preferences
            user.preferences = preferences

            LOGGER.debug(f"Updated preferences for user {user.username}")
            self.save()

    def _load(self) -> None:
        """Load users from storage."""
        LOGGER.debug("Loading data from auth store")
        data = self._auth_store.load()

        users: dict[str, User] = {}
        refresh_tokens: dict[str, RefreshToken] = {}
        access_tokens: dict[str, AccessToken] = {}

        for user in data.get("users", {}).values():
            preferences: Preferences | None = None
            if preferences_dict := user.get("preferences", None):
                preferences = Preferences(**preferences_dict)

            users[user["id"]] = User(
                name=user["name"],
                username=user["username"],
                password=user["password"],
                # Group was renamed to role, make sure it is backwards compatible
                role=Role(user["group"] if user.get("group", False) else user["role"]),
                id=user["id"],
                enabled=user["enabled"],
                assigned_cameras=user.get("assigned_cameras", None),
                preferences=preferences,
            )

        for refresh_token in data.get("refresh_tokens", {}).values():
            refresh_tokens[refresh_token["id"]] = RefreshToken(
                user_id=refresh_token["user_id"],
                client_id=refresh_token["client_id"],
                session_expiration=datetime.timedelta(
                    seconds=refresh_token["session_expiration"]
                ),
                access_token_type=refresh_token["access_token_type"],
                access_token_expiration=datetime.timedelta(
                    seconds=refresh_token["access_token_expiration"]
                ),
                created_at=refresh_token["created_at"],
                id=refresh_token["id"],
                token=refresh_token["token"],
                jwt_key=refresh_token["jwt_key"],
                static_asset_key=refresh_token["static_asset_key"],
                used_at=refresh_token["used_at"],
                used_by=refresh_token["used_by"],
            )

        for pat in data.get("access_tokens", {}).values():
            access_tokens[pat["id"]] = AccessToken(
                user_id=pat["user_id"],
                name=pat["name"],
                token_hash=pat["token_hash"],
                id=pat["id"],
                created_at=pat["created_at"],
                expires_at=pat.get("expires_at"),
                last_used_at=pat.get("last_used_at"),
                last_used_by=pat.get("last_used_by"),
            )

        self._users = users
        self._refresh_tokens = refresh_tokens
        self._access_tokens = access_tokens

    def save(self) -> None:
        """Save users to storage."""
        self._auth_store.save(
            {
                "users": self.users,
                "refresh_tokens": self.refresh_tokens,
                "access_tokens": {t.id: asdict(t) for t in self.access_tokens.values()},
            }
        )

    def generate_refresh_token(
        self,
        user_id: str,
        client_id: str,
        access_token_type: Literal["normal"],
        access_token_expiration: datetime.timedelta = ACCESS_TOKEN_EXPIRATION,
    ) -> RefreshToken:
        """Generate refresh token."""
        refresh_token = RefreshToken(
            user_id=user_id,
            client_id=client_id,
            session_expiration=(self.session_expiry or datetime.timedelta(days=3650)),
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

    def delete_refresh_token(self, refresh_token: RefreshToken) -> None:
        """Delete refresh token."""
        if refresh_token.id in self.refresh_tokens:
            del self.refresh_tokens[refresh_token.id]
            self.save()

    def validate_refresh_token(self, refresh_token: RefreshToken) -> None:
        """Validate refresh token."""

    def generate_access_token(
        self,
        refresh_token: RefreshToken,
        remote_ip: str | None,
        expiry: datetime.timedelta | None = None,
    ) -> str:
        """Generate access token using JWT."""
        self.validate_refresh_token(refresh_token)
        now = utcnow()
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

    def validate_access_token(self, access_token: str) -> None | RefreshToken:
        """Validate access token."""
        try:
            unverif_claims = jwt.decode(
                access_token, algorithms=["HS256"], options={"verify_signature": False}
            )
        except jwt.InvalidTokenError:
            return None

        refresh_token = self.get_refresh_token(cast("str", unverif_claims.get("iss")))
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

    def create_access_token(
        self,
        user_id: str,
        name: str,
        expires_at: float | None = None,
    ) -> tuple[AccessToken, str]:
        """Create a new personal access token.

        Returns the AccessToken record and the raw token string.
        The raw token is only available at creation time and only its hash is stored.
        """
        name = name.strip()
        if not name:
            raise ValueError("Token name cannot be empty")
        if len(name) > MAX_TOKEN_NAME_LENGTH:
            raise ValueError(
                f"Token name cannot exceed {MAX_TOKEN_NAME_LENGTH} characters"
            )

        with self._user_lock:
            user_tokens = [
                t for t in self.access_tokens.values() if t.user_id == user_id
            ]
            if len(user_tokens) >= MAX_ACCESS_TOKENS_PER_USER:
                raise AccessTokenLimitExceededError(
                    f"Maximum of {MAX_ACCESS_TOKENS_PER_USER} personal access tokens "
                    "per user exceeded"
                )

            raw_token = "vpat_" + secrets.token_hex(64)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            token = AccessToken(
                user_id=user_id,
                name=name,
                token_hash=token_hash,
                expires_at=expires_at,
            )
            self.access_tokens[token.id] = token
            self.save()

        return token, raw_token

    def get_access_tokens_for_user(self, user_id: str) -> list[AccessToken]:
        """Return all personal access tokens for a user."""
        return [t for t in self.access_tokens.values() if t.user_id == user_id]

    def delete_access_token(self, token_id: str, user_id: str) -> None:
        """Delete a personal access token.

        Raises AccessTokenNotFoundError if the token does not exist or does not
        belong to the given user.
        """
        with self._user_lock:
            token = self.access_tokens.get(token_id)
            if token is None or token.user_id != user_id:
                raise AccessTokenNotFoundError(f"Access token {token_id} not found")
            self._pat_last_used_persisted_at.pop(token_id, None)
            del self.access_tokens[token_id]
            self.save()

    def validate_access_token_pat(self, raw_token: str) -> AccessToken | None:
        """Validate a raw personal access token string.

        Computes the SHA-256 hash of the supplied token and performs a
        timing-safe comparison against every stored hash to prevent timing attacks.
        Returns the matching AccessToken, or None if not found / expired.
        """
        incoming_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        found: AccessToken | None = None

        with self._user_lock:
            tokens_snapshot = list(self.access_tokens.values())

        for token in tokens_snapshot:
            if hmac.compare_digest(incoming_hash, token.token_hash):
                found = token

        if found is None:
            return None

        # Reject expired tokens
        if found.expires_at is not None and utcnow().timestamp() > found.expires_at:
            return None

        return found

    def update_pat_used(self, pat: AccessToken, remote_ip: str) -> None:
        """Update the last-used metadata for a personal access token."""
        now = utcnow().timestamp()

        with self._user_lock:
            stored_pat = self.access_tokens.get(pat.id)
            if stored_pat is None:
                return

            last_persisted_at = self._pat_last_used_persisted_at.get(
                stored_pat.id,
                stored_pat.last_used_at or 0,
            )
            should_save = (
                stored_pat.last_used_at is None
                or stored_pat.last_used_by != remote_ip
                or now - last_persisted_at
                >= PAT_LAST_USED_SAVE_INTERVAL.total_seconds()
            )

            stored_pat.last_used_at = now
            stored_pat.last_used_by = remote_ip

            if should_save:
                self.save()
                self._pat_last_used_persisted_at[stored_pat.id] = now

    def revoke_all_for_user(self, user_id: str) -> None:
        """Revoke all sessions (refresh tokens) and personal access tokens for a user.

        This is a destructive, irreversible operation that forces the user to
        re-authenticate on all devices and invalidates all PATs.
        """
        with self._user_lock:
            # Remove all refresh tokens belonging to the user
            rt_ids_to_delete = [
                rt_id
                for rt_id, rt in self.refresh_tokens.items()
                if rt.user_id == user_id
            ]
            for rt_id in rt_ids_to_delete:
                del self.refresh_tokens[rt_id]

            # Remove all PATs belonging to the user
            pat_ids_to_delete = [
                t_id for t_id, t in self.access_tokens.items() if t.user_id == user_id
            ]
            for t_id in pat_ids_to_delete:
                self._pat_last_used_persisted_at.pop(t_id, None)
                del self.access_tokens[t_id]

            self.save()
