"""Authentication."""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING, Literal

import bcrypt

from viseron.components.webserver.const import STORAGE_KEY
from viseron.exceptions import ViseronError
from viseron.helpers.storage import Storage

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)


class UserExistsError(ViseronError):
    """User already exists."""


@dataclass
class User:
    """User."""

    name: str
    username: str
    password: str
    group: Literal["admin", "user"]


class Auth:
    """Users."""

    def __init__(self, vis: Viseron):
        self._vis = vis
        self.auth_store = Storage(vis, STORAGE_KEY)
        self._lock = Lock()

    @property
    def users(self):
        """Return users."""
        return self.auth_store.data

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
        group: Literal["admin", "user"] = None,
    ):
        """Add user."""
        name = name.strip()
        username = username.strip().casefold()
        with self._lock:
            if username in self.users:
                raise UserExistsError(f"A user with username {username} already exists")

            if group is None:
                if not self.users:
                    LOGGER.debug("No users exist, setting group to admin")
                    group = "admin"
                else:
                    LOGGER.debug("No group specified, setting group to user")
                    group = "user"

            self.users[username] = User(
                name, username, self.hash_password(password), group
            )
            self.save()

    def save(self):
        """Save users to storage."""
        self.auth_store.save(self.users)
