"""LDAP API Handler."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

import voluptuous as vol
from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.comments import CommentedMap

from viseron.components.webserver.api.handlers import BaseAPIHandler, require_auth
from viseron.components.webserver.auth import AuthenticationFailedError, Role
from viseron.components.webserver.const import (
    COMPONENT as WEBSERVER_COMPONENT,
    CONFIG_ADMIN_GROUPS,
    CONFIG_AUTH,
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
    DEFAULT_LDAP_DEFAULT_ROLE,
    DEFAULT_LDAP_GROUP_FILTER,
    DEFAULT_LDAP_NAME_ATTRIBUTE,
    DEFAULT_LDAP_USER_FILTER,
    DEFAULT_LDAP_USERNAME_ATTRIBUTE,
)
from viseron.components.webserver.ldap_auth import (
    LDAPAuthenticator,
    LDAPTestFailedError,
)
from viseron.const import CONFIG_PATH
from viseron.reload import reload_config

LDAP_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_ENABLED): bool,
        vol.Optional(CONFIG_URL, default=""): str,
        vol.Optional(CONFIG_BIND_DN, default=""): str,
        vol.Optional(CONFIG_BIND_PASSWORD, default=""): str,
        vol.Optional(CONFIG_USER_BASE_DN, default=""): str,
        vol.Optional(CONFIG_USER_FILTER, default=DEFAULT_LDAP_USER_FILTER): str,
        vol.Optional(
            CONFIG_USERNAME_ATTRIBUTE,
            default=DEFAULT_LDAP_USERNAME_ATTRIBUTE,
        ): str,
        vol.Optional(CONFIG_NAME_ATTRIBUTE, default=DEFAULT_LDAP_NAME_ATTRIBUTE): str,
        vol.Optional(CONFIG_GROUP_BASE_DN, default=""): str,
        vol.Optional(CONFIG_GROUP_FILTER, default=DEFAULT_LDAP_GROUP_FILTER): str,
        vol.Optional(CONFIG_ADMIN_GROUPS, default=[]): [str],
        vol.Optional(CONFIG_WRITE_GROUPS, default=[]): [str],
        vol.Optional(CONFIG_READ_GROUPS, default=[]): [str],
        vol.Optional(CONFIG_DEFAULT_ROLE, default=DEFAULT_LDAP_DEFAULT_ROLE): vol.In(
            ["admin", "read", "write"]
        ),
        vol.Optional("bind_password_set", default=False): bool,
    }
)


class LdapAPIHandler(BaseAPIHandler):
    """Handler for API calls related to LDAP authentication."""

    routes = [
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/ldap",
            "supported_methods": ["GET"],
            "method": "get_ldap_config",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/ldap",
            "supported_methods": ["PUT"],
            "method": "save_ldap_config",
            "json_body_schema": vol.Schema(
                {vol.Required("config"): LDAP_CONFIG_SCHEMA}
            ),
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/ldap/test",
            "supported_methods": ["POST"],
            "method": "test_ldap_config",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("config"): LDAP_CONFIG_SCHEMA,
                    vol.Optional("username", default=""): str,
                    vol.Optional("password", default=""): str,
                }
            ),
        },
    ]

    def _yaml(self) -> YAML:
        """Return configured YAML parser."""
        yaml = YAML(typ="rt")
        yaml.preserve_quotes = True
        return yaml

    def _load_config(self) -> dict[str, Any]:
        """Load and parse config.yaml."""
        with open(CONFIG_PATH, encoding="utf-8") as config_file:
            return self._yaml().load(config_file) or {}

    def _save_config(self, config: dict[str, Any]) -> None:
        """Save config.yaml."""
        with open(CONFIG_PATH, "w", encoding="utf-8") as config_file:
            self._yaml().dump(config, config_file)

    @staticmethod
    def _plain_value(value: Any) -> str:
        """Return a plain string from ruamel scalar types."""
        if value is None:
            return ""
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    def _current_ldap_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Return LDAP config from config.yaml."""
        webserver_config = config.get(WEBSERVER_COMPONENT) or {}
        auth_config = webserver_config.get(CONFIG_AUTH) or {}
        return auth_config.get(CONFIG_LDAP) or {}

    def _sanitize_ldap_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Return LDAP config for UI consumption."""
        bind_password = config.get(CONFIG_BIND_PASSWORD)
        return {
            CONFIG_ENABLED: bool(config),
            CONFIG_URL: self._plain_value(config.get(CONFIG_URL)),
            CONFIG_BIND_DN: self._plain_value(config.get(CONFIG_BIND_DN)),
            CONFIG_BIND_PASSWORD: "",
            "bind_password_set": bool(bind_password),
            CONFIG_USER_BASE_DN: self._plain_value(config.get(CONFIG_USER_BASE_DN)),
            CONFIG_USER_FILTER: self._plain_value(
                config.get(CONFIG_USER_FILTER) or DEFAULT_LDAP_USER_FILTER
            ),
            CONFIG_USERNAME_ATTRIBUTE: self._plain_value(
                config.get(CONFIG_USERNAME_ATTRIBUTE)
                or DEFAULT_LDAP_USERNAME_ATTRIBUTE
            ),
            CONFIG_NAME_ATTRIBUTE: self._plain_value(
                config.get(CONFIG_NAME_ATTRIBUTE) or DEFAULT_LDAP_NAME_ATTRIBUTE
            ),
            CONFIG_GROUP_BASE_DN: self._plain_value(config.get(CONFIG_GROUP_BASE_DN)),
            CONFIG_GROUP_FILTER: self._plain_value(
                config.get(CONFIG_GROUP_FILTER) or DEFAULT_LDAP_GROUP_FILTER
            ),
            CONFIG_ADMIN_GROUPS: list(config.get(CONFIG_ADMIN_GROUPS) or []),
            CONFIG_WRITE_GROUPS: list(config.get(CONFIG_WRITE_GROUPS) or []),
            CONFIG_READ_GROUPS: list(config.get(CONFIG_READ_GROUPS) or []),
            CONFIG_DEFAULT_ROLE: self._plain_value(
                config.get(CONFIG_DEFAULT_ROLE) or DEFAULT_LDAP_DEFAULT_ROLE
            ),
        }

    def _parse_bind_password(self, value: str) -> Any:
        """Parse plain password or !secret reference."""
        password = value.strip()
        if password.startswith("!secret "):
            return self._yaml().load(f"value: {password}\n")["value"]
        return value or None

    def _normalized_ldap_config(
        self,
        ldap_config: dict[str, Any],
        existing_ldap_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Normalize UI LDAP config to backend config."""
        if not ldap_config[CONFIG_ENABLED]:
            return {}

        if not ldap_config[CONFIG_URL].strip():
            raise ValueError("LDAP URL is required")
        if not ldap_config[CONFIG_USER_BASE_DN].strip():
            raise ValueError("User base DN is required")

        existing_bind_password = None
        if existing_ldap_config:
            existing_bind_password = existing_ldap_config.get(CONFIG_BIND_PASSWORD)

        bind_password = self._parse_bind_password(ldap_config[CONFIG_BIND_PASSWORD])
        if bind_password is None and existing_bind_password:
            bind_password = existing_bind_password

        normalized = {
            CONFIG_ENABLED: True,
            CONFIG_URL: ldap_config[CONFIG_URL].strip(),
            CONFIG_BIND_DN: ldap_config[CONFIG_BIND_DN].strip() or None,
            CONFIG_BIND_PASSWORD: bind_password,
            CONFIG_USER_BASE_DN: ldap_config[CONFIG_USER_BASE_DN].strip(),
            CONFIG_USER_FILTER: ldap_config[CONFIG_USER_FILTER].strip()
            or DEFAULT_LDAP_USER_FILTER,
            CONFIG_USERNAME_ATTRIBUTE: ldap_config[
                CONFIG_USERNAME_ATTRIBUTE
            ].strip()
            or DEFAULT_LDAP_USERNAME_ATTRIBUTE,
            CONFIG_NAME_ATTRIBUTE: ldap_config[CONFIG_NAME_ATTRIBUTE].strip()
            or DEFAULT_LDAP_NAME_ATTRIBUTE,
            CONFIG_GROUP_BASE_DN: ldap_config[CONFIG_GROUP_BASE_DN].strip() or None,
            CONFIG_GROUP_FILTER: ldap_config[CONFIG_GROUP_FILTER].strip()
            or DEFAULT_LDAP_GROUP_FILTER,
            CONFIG_ADMIN_GROUPS: ldap_config[CONFIG_ADMIN_GROUPS],
            CONFIG_WRITE_GROUPS: ldap_config[CONFIG_WRITE_GROUPS],
            CONFIG_READ_GROUPS: ldap_config[CONFIG_READ_GROUPS],
            CONFIG_DEFAULT_ROLE: ldap_config[CONFIG_DEFAULT_ROLE],
        }
        return normalized

    def _write_ldap_config(
        self,
        config: dict[str, Any],
        ldap_config: dict[str, Any],
    ) -> None:
        """Write LDAP config into full config."""
        webserver_config = config.setdefault(WEBSERVER_COMPONENT, CommentedMap())
        auth_config = webserver_config.setdefault(CONFIG_AUTH, CommentedMap())
        if ldap_config:
            auth_config[CONFIG_LDAP] = CommentedMap(ldap_config)
        else:
            auth_config.pop(CONFIG_LDAP, None)

    @require_auth
    async def get_ldap_config(self) -> None:
        """Return LDAP configuration."""
        config = await self.run_in_executor(self._load_config)
        ldap_config = self._sanitize_ldap_config(self._current_ldap_config(config))
        await self.response_success(response={"config": ldap_config})

    @require_auth
    async def save_ldap_config(self) -> None:
        """Save LDAP configuration."""

        def _save() -> dict[str, Any]:
            config = self._load_config()
            current_ldap_config = self._current_ldap_config(config)
            ldap_config = self._normalized_ldap_config(
                self.json_body["config"], current_ldap_config
            )
            self._write_ldap_config(config, ldap_config)
            self._save_config(config)
            result = reload_config(self._vis)
            return {
                "success": result.success,
                "restart_required": result.restart_required,
                "errors": [str(error) for error in result.errors],
            }

        try:
            result = await self.run_in_executor(_save)
        except (ValueError, YAMLError) as error:
            self.response_error(HTTPStatus.BAD_REQUEST, str(error))
            return

        await self.response_success(response=result)

    @require_auth
    async def test_ldap_config(self) -> None:
        """Test LDAP configuration."""

        def _test() -> dict[str, Any]:
            config = self._load_config()
            ldap_config = self._normalized_ldap_config(
                self.json_body["config"],
                self._current_ldap_config(config),
            )
            username = self.json_body["username"].strip()
            password = self.json_body["password"]
            if username and not password:
                raise ValueError("Password is required when testing a user")

            authenticator = LDAPAuthenticator({CONFIG_LDAP: ldap_config})
            return authenticator.test_connection(username or None, password or None)

        try:
            result = await self.run_in_executor(_test)
        except ValueError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, str(error))
            return
        except LDAPTestFailedError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, str(error))
            return
        except AuthenticationFailedError:
            self.response_error(HTTPStatus.BAD_REQUEST, "LDAP test failed")
            return
        except YAMLError as error:
            self.response_error(HTTPStatus.BAD_REQUEST, str(error))
            return

        await self.response_success(response=result)
