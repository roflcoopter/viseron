"""Camera access API handler."""

from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any

import voluptuous as vol
from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from viseron.components.webserver.api.handlers import BaseAPIHandler, require_auth
from viseron.components.webserver.auth import Role
from viseron.components.webserver.const import (
    COMPONENT as WEBSERVER_COMPONENT,
    CONFIG_AUTH,
    CONFIG_CAMERA_GROUPS,
    CONFIG_CAMERAS,
    CONFIG_GROUPS,
    CONFIG_LDAP_CAMERA_ACCESS,
)
from viseron.const import CONFIG_PATH
from viseron.reload import reload_config

CAMERA_ACCESS_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_CAMERA_GROUPS): [
            {
                vol.Required("id"): str,
                vol.Required("name"): str,
                vol.Required(CONFIG_CAMERAS): [str],
            }
        ],
        vol.Required(CONFIG_LDAP_CAMERA_ACCESS): [
            {
                vol.Required(CONFIG_GROUPS): [str],
                vol.Required(CONFIG_CAMERA_GROUPS): [str],
                vol.Required(CONFIG_CAMERAS): [str],
            }
        ],
    }
)

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


class CameraaccessAPIHandler(BaseAPIHandler):
    """Handler for camera access settings."""

    routes = [
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/cameraaccess",
            "supported_methods": ["GET"],
            "method": "get_camera_access_config",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/cameraaccess",
            "supported_methods": ["PUT"],
            "method": "save_camera_access_config",
            "json_body_schema": vol.Schema(
                {vol.Required("config"): CAMERA_ACCESS_CONFIG_SCHEMA}
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
    def _auth_config(config: dict[str, Any]) -> dict[str, Any]:
        webserver_config = config.get(WEBSERVER_COMPONENT) or {}
        return webserver_config.get(CONFIG_AUTH) or {}

    @staticmethod
    def _sanitize_config(auth_config: dict[str, Any]) -> dict[str, Any]:
        camera_groups = []
        for group_id, group in (auth_config.get(CONFIG_CAMERA_GROUPS) or {}).items():
            camera_groups.append(
                {
                    "id": str(group_id),
                    "name": str(group.get("name") or group_id),
                    CONFIG_CAMERAS: list(group.get(CONFIG_CAMERAS) or []),
                }
            )

        return {
            CONFIG_CAMERA_GROUPS: camera_groups,
            CONFIG_LDAP_CAMERA_ACCESS: [
                {
                    CONFIG_GROUPS: list(rule.get(CONFIG_GROUPS) or []),
                    CONFIG_CAMERA_GROUPS: list(rule.get(CONFIG_CAMERA_GROUPS) or []),
                    CONFIG_CAMERAS: list(rule.get(CONFIG_CAMERAS) or []),
                }
                for rule in auth_config.get(CONFIG_LDAP_CAMERA_ACCESS) or []
            ],
        }

    @staticmethod
    def _normalize_config(config: dict[str, Any]) -> dict[str, Any]:
        seen_group_ids: set[str] = set()
        camera_groups = CommentedMap()

        for group in config[CONFIG_CAMERA_GROUPS]:
            group_id = group["id"].strip()
            if not IDENTIFIER_PATTERN.match(group_id):
                raise ValueError(
                    f"Camera group id '{group_id}' must contain only letters, "
                    "numbers and underscores"
                )
            if group_id in seen_group_ids:
                raise ValueError(f"Duplicate camera group id '{group_id}'")
            seen_group_ids.add(group_id)

            camera_group = CommentedMap()
            camera_group["name"] = group["name"].strip() or group_id
            camera_group[CONFIG_CAMERAS] = CommentedSeq(
                list(dict.fromkeys(group[CONFIG_CAMERAS]))
            )
            camera_groups[group_id] = camera_group

        rules = CommentedSeq()
        for rule in config[CONFIG_LDAP_CAMERA_ACCESS]:
            missing_groups = [
                group_id
                for group_id in rule[CONFIG_CAMERA_GROUPS]
                if group_id not in seen_group_ids
            ]
            if missing_groups:
                raise ValueError(
                    "LDAP access rule references unknown camera groups: "
                    + ", ".join(missing_groups)
                )

            normalized_rule = CommentedMap()
            normalized_rule[CONFIG_GROUPS] = CommentedSeq(
                [
                    group.strip()
                    for group in dict.fromkeys(rule[CONFIG_GROUPS])
                    if group.strip()
                ]
            )
            normalized_rule[CONFIG_CAMERA_GROUPS] = CommentedSeq(
                list(dict.fromkeys(rule[CONFIG_CAMERA_GROUPS]))
            )
            normalized_rule[CONFIG_CAMERAS] = CommentedSeq(
                list(dict.fromkeys(rule[CONFIG_CAMERAS]))
            )
            if normalized_rule[CONFIG_GROUPS]:
                rules.append(normalized_rule)

        return {
            CONFIG_CAMERA_GROUPS: camera_groups,
            CONFIG_LDAP_CAMERA_ACCESS: rules,
        }

    @staticmethod
    def _write_camera_access_config(
        config: dict[str, Any], camera_access_config: dict[str, Any]
    ) -> None:
        webserver_config = config.setdefault(WEBSERVER_COMPONENT, CommentedMap())
        auth_config = webserver_config.setdefault(CONFIG_AUTH, CommentedMap())
        auth_config[CONFIG_CAMERA_GROUPS] = camera_access_config[CONFIG_CAMERA_GROUPS]
        auth_config[CONFIG_LDAP_CAMERA_ACCESS] = camera_access_config[
            CONFIG_LDAP_CAMERA_ACCESS
        ]

    @require_auth
    async def get_camera_access_config(self) -> None:
        """Return camera access configuration."""
        config = await self.run_in_executor(self._load_config)
        await self.response_success(
            response={"config": self._sanitize_config(self._auth_config(config))}
        )

    @require_auth
    async def save_camera_access_config(self) -> None:
        """Save camera access configuration."""

        def _save() -> dict[str, Any]:
            config = self._load_config()
            camera_access_config = self._normalize_config(self.json_body["config"])
            self._write_camera_access_config(config, camera_access_config)
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
