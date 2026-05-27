"""LDAP authentication."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ldap3 import ALL_ATTRIBUTES, Connection, Server
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from viseron.components.webserver.auth import AuthenticationFailedError, Role
from viseron.components.webserver.const import (
    CONFIG_ADMIN_GROUPS,
    CONFIG_BIND_DN,
    CONFIG_BIND_PASSWORD,
    CONFIG_DEFAULT_ROLE,
    CONFIG_ENABLED,
    CONFIG_GROUP_BASE_DN,
    CONFIG_GROUP_FILTER,
    CONFIG_LDAP,
    CONFIG_NAME_ATTRIBUTE,
    CONFIG_READ_GROUPS,
    CONFIG_URL,
    CONFIG_USER_BASE_DN,
    CONFIG_USER_FILTER,
    CONFIG_USERNAME_ATTRIBUTE,
    CONFIG_WRITE_GROUPS,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class LDAPUser:
    """Authenticated LDAP user."""

    username: str
    name: str
    role: Role


class LDAPTestFailedError(AuthenticationFailedError):
    """LDAP connection test failed."""


class LDAPUserBindFailedError(AuthenticationFailedError):
    """LDAP user bind failed."""


class LDAPAuthorizationFailedError(AuthenticationFailedError):
    """LDAP user is not authorized by group rules."""


class LDAPAuthenticator:
    """Authenticate users against LDAP or Active Directory."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config.get(CONFIG_LDAP) or {}

    @property
    def enabled(self) -> bool:
        """Return if LDAP auth is enabled."""
        return bool(self._config and self._config[CONFIG_ENABLED])

    @property
    def _server(self) -> Server:
        """Return LDAP server."""
        return Server(self._config[CONFIG_URL], get_info=None)

    def _service_connection(self) -> Connection:
        """Return a bound service connection."""
        bind_dn = self._config.get(CONFIG_BIND_DN)
        bind_password = self._config.get(CONFIG_BIND_PASSWORD)

        connection = Connection(
            self._server,
            user=bind_dn,
            password=bind_password,
            auto_bind=True,
        )
        return connection

    def _search_user(
        self, connection: Connection, username: str
    ) -> tuple[str, dict[str, Any]]:
        """Search LDAP for username and return DN and attributes."""
        escaped_username = escape_filter_chars(username)
        user_filter = self._config[CONFIG_USER_FILTER].format(
            username=escaped_username
        )

        connection.search(
            search_base=self._config[CONFIG_USER_BASE_DN],
            search_filter=user_filter,
            attributes=ALL_ATTRIBUTES,
            size_limit=2,
        )
        if len(connection.entries) != 1:
            raise AuthenticationFailedError

        entry = connection.entries[0]
        return str(entry.entry_dn), entry.entry_attributes_as_dict

    def _bind_domain(self) -> str | None:
        """Return domain from bind DN when it uses UPN format."""
        bind_dn = self._config.get(CONFIG_BIND_DN) or ""
        if "@" not in bind_dn:
            return None
        return bind_dn.rsplit("@", 1)[1]

    def _netbios_domain(self) -> str | None:
        """Return a likely NetBIOS domain from the bind domain."""
        domain = self._bind_domain()
        if not domain:
            return None
        return domain.split(".", maxsplit=1)[0].upper()

    @staticmethod
    def _search_username(username: str) -> str:
        """Return the username part used for LDAP search."""
        if "\\" in username:
            return username.rsplit("\\", maxsplit=1)[1]
        if "@" in username:
            return username.split("@", maxsplit=1)[0]
        return username

    def _user_bind_candidates(
        self,
        user_dn: str,
        username: str,
        search_username: str,
        attributes: dict[str, Any],
    ) -> list[str]:
        """Return candidate bind names for an LDAP user."""
        candidates = [user_dn]
        if user_principal_name := self._attribute_value(
            attributes, "userPrincipalName"
        ):
            candidates.append(user_principal_name)
        if "\\" in username or "@" in username:
            candidates.append(username)
        elif domain := self._bind_domain():
            candidates.append(f"{search_username}@{domain}")
        if netbios_domain := self._netbios_domain():
            candidates.append(f"{netbios_domain}\\{search_username}")
        return list(dict.fromkeys(candidates))

    def _validate_user_password(
        self,
        user_dn: str,
        username: str,
        attributes: dict[str, Any],
        password: str,
    ) -> None:
        """Validate user password with a user bind."""
        if not password:
            raise AuthenticationFailedError
        search_username = self._search_username(username)
        failure_messages: list[str] = []
        for bind_user in self._user_bind_candidates(
            user_dn, username, search_username, attributes
        ):
            connection: Connection | None = None
            try:
                connection = Connection(
                    self._server,
                    user=bind_user,
                    password=password,
                )
                if connection.bind():
                    connection.unbind()
                    return
                failure_messages.append(self._bind_result_message(connection.result))
                LOGGER.debug(
                    "LDAP user bind failed for %s: %s",
                    bind_user,
                    connection.result,
                )
                connection.unbind()
            except LDAPException as error:
                failure_messages.append(str(error))
                LOGGER.debug("LDAP user bind failed for %s: %s", bind_user, error)
                if connection is not None:
                    connection.unbind()
        if failure_messages:
            unique_messages = dict.fromkeys(
                message for message in failure_messages if message
            )
            raise LDAPUserBindFailedError(
                "User bind failed: " + "; ".join(unique_messages)
            )
        raise AuthenticationFailedError

    @staticmethod
    def _bind_result_message(result: dict[str, Any]) -> str:
        """Return a useful message for an LDAP bind result."""
        description = result.get("description")
        message = result.get("message")
        if description and message:
            return f"{description} - {message}"
        if description:
            return str(description)
        if message:
            return str(message)
        return "bind failed"

    def _search_groups(
        self, connection: Connection, username: str, user_dn: str
    ) -> list[str]:
        """Return groups for user from memberOf and optional group search."""
        groups: list[str] = []
        escaped_username = escape_filter_chars(username)
        escaped_user_dn = escape_filter_chars(user_dn)

        if group_base_dn := self._config.get(CONFIG_GROUP_BASE_DN):
            group_filter = self._config[CONFIG_GROUP_FILTER].format(
                username=escaped_username,
                user_dn=escaped_user_dn,
            )
            connection.search(
                search_base=group_base_dn,
                search_filter=group_filter,
                attributes=ALL_ATTRIBUTES,
            )
            groups.extend(str(entry.entry_dn) for entry in connection.entries)

        return groups

    @staticmethod
    def _attribute_value(attributes: dict[str, Any], key: str) -> str | None:
        """Return first LDAP attribute value as string."""
        value = attributes.get(key)
        if isinstance(value, list):
            if not value:
                return None
            return str(value[0])
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _member_of(attributes: dict[str, Any]) -> list[str]:
        """Return memberOf groups."""
        member_of = attributes.get("memberOf") or attributes.get("memberof") or []
        if isinstance(member_of, list):
            return [str(group) for group in member_of]
        return [str(member_of)]

    @staticmethod
    def _group_matches(groups: list[str], configured_groups: list[str]) -> bool:
        """Return if user groups match configured groups."""
        normalized_groups = [group.casefold() for group in groups]
        for configured_group in configured_groups:
            configured = configured_group.casefold()
            for group in normalized_groups:
                if configured == group:
                    return True
                if group.startswith(f"cn={configured},"):
                    return True
        return False

    def _role_from_groups(self, groups: list[str]) -> Role:
        """Return Viseron role from LDAP groups."""
        if self._group_matches(groups, self._config[CONFIG_ADMIN_GROUPS]):
            return Role.ADMIN
        if self._group_matches(groups, self._config[CONFIG_WRITE_GROUPS]):
            return Role.WRITE
        if self._group_matches(groups, self._config[CONFIG_READ_GROUPS]):
            return Role.READ
        if self._config[CONFIG_DEFAULT_ROLE] == "deny":
            raise LDAPAuthorizationFailedError(
                "User is not in an allowed LDAP group"
            )
        return Role(self._config[CONFIG_DEFAULT_ROLE])

    def authenticate(self, username: str, password: str) -> LDAPUser:
        """Authenticate username and password against LDAP."""
        username = username.strip().casefold()
        search_username = self._search_username(username)
        connection: Connection | None = None
        try:
            connection = self._service_connection()
            user_dn, attributes = self._search_user(connection, search_username)
            self._validate_user_password(user_dn, username, attributes, password)

            groups = self._member_of(attributes)
            groups.extend(self._search_groups(connection, username, user_dn))
            role = self._role_from_groups(groups)

            ldap_username = (
                self._attribute_value(
                    attributes, self._config[CONFIG_USERNAME_ATTRIBUTE]
                )
                or username
            )
            name = (
                self._attribute_value(attributes, self._config[CONFIG_NAME_ATTRIBUTE])
                or ldap_username
            )
            return LDAPUser(ldap_username.casefold(), name, role)
        except (LDAPException, AuthenticationFailedError) as error:
            LOGGER.debug("LDAP authentication failed for %s: %s", username, error)
            raise AuthenticationFailedError from error
        finally:
            if connection is not None:
                connection.unbind()

    def test_connection(
        self, username: str | None = None, password: str | None = None
    ) -> dict[str, Any]:
        """Test LDAP bind and optionally user authentication."""
        connection: Connection | None = None
        try:
            connection = self._service_connection()
            if not username:
                return {"bind": True, "user": None}

            username = username.strip().casefold()
            search_username = self._search_username(username)
            user_dn, attributes = self._search_user(connection, search_username)
            if password:
                self._validate_user_password(user_dn, username, attributes, password)

            groups = self._member_of(attributes)
            groups.extend(self._search_groups(connection, username, user_dn))
            role = self._role_from_groups(groups)
            ldap_username = (
                self._attribute_value(
                    attributes, self._config[CONFIG_USERNAME_ATTRIBUTE]
                )
                or username
            )
            name = (
                self._attribute_value(attributes, self._config[CONFIG_NAME_ATTRIBUTE])
                or ldap_username
            )
            return {
                "bind": True,
                "user": {
                    "username": ldap_username.casefold(),
                    "name": name,
                    "role": role.value,
                    "groups": len(groups),
                    "password_validated": bool(password),
                },
            }
        except LDAPUserBindFailedError as error:
            LOGGER.debug("LDAP connection test failed: %s", error)
            raise LDAPTestFailedError(str(error)) from error
        except LDAPAuthorizationFailedError as error:
            LOGGER.debug("LDAP connection test failed: %s", error)
            raise LDAPTestFailedError(str(error)) from error
        except LDAPException as error:
            LOGGER.debug("LDAP connection test failed: %s", error)
            raise LDAPTestFailedError(str(error)) from error
        except AuthenticationFailedError as error:
            LOGGER.debug("LDAP connection test failed: %s", error)
            raise LDAPTestFailedError(
                "User search did not return exactly one user"
            ) from error
        finally:
            if connection is not None:
                connection.unbind()
