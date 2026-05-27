"""Cameras API Handler."""
from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

import voluptuous as vol
from ruamel.yaml import YAML, YAMLError

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import Role
from viseron.const import CONFIG_PATH
from viseron.reload import reload_config

LOGGER = logging.getLogger(__name__)


CAMERA_IDENTIFIER_SCHEMA = vol.All(str, vol.Match(r"^[A-Za-z0-9_]+$"))
STREAM_FORMATS = ["rtsp", "mjpeg"]


def _optional_trimmed_string(value: str | None) -> str | None:
    """Return stripped string or None."""
    if value is None:
        return None
    value = value.strip()
    return value or None


class CamerasAPIHandler(BaseAPIHandler):
    """Handler for API calls related to cameras."""

    routes = [
        {
            "path_pattern": r"/cameras",
            "supported_methods": ["GET"],
            "method": "get_cameras_endpoint",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/cameras",
            "supported_methods": ["POST"],
            "method": "post_camera_config",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("identifier"): CAMERA_IDENTIFIER_SCHEMA,
                    vol.Required("name"): vol.All(str, vol.Length(min=1)),
                    vol.Required("host"): vol.All(str, vol.Length(min=1)),
                    vol.Optional("port", default=554): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                    vol.Required("path"): vol.All(str, vol.Length(min=1)),
                    vol.Optional("stream_format", default="rtsp"): vol.In(
                        STREAM_FORMATS
                    ),
                    vol.Optional("username", default=None): vol.Maybe(str),
                    vol.Optional("password", default=None): vol.Maybe(str),
                    vol.Optional("substream_path", default=None): vol.Maybe(str),
                    vol.Optional("substream_port", default=554): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                    vol.Optional("substream_stream_format", default="rtsp"): vol.In(
                        STREAM_FORMATS
                    ),
                    vol.Optional("idle_timeout", default=5): vol.All(
                        vol.Coerce(int), vol.Range(min=0)
                    ),
                    vol.Optional("enable_recorder", default=True): bool,
                    vol.Optional("enable_nvr", default=True): bool,
                    vol.Optional("reload", default=True): bool,
                }
            ),
        },
        {
            "path_pattern": r"/cameras/failed",
            "supported_methods": ["GET"],
            "method": "get_failed_cameras_endpoint",
        },
    ]

    @staticmethod
    def _yaml() -> YAML:
        """Return configured YAML parser."""
        yaml = YAML(typ="rt")
        yaml.preserve_quotes = True
        return yaml

    def _load_raw_config(self) -> tuple[dict[str, Any], str]:
        """Load config.yaml and return parsed and raw config."""
        with open(CONFIG_PATH, encoding="utf-8") as config_file:
            raw_config = config_file.read()
        config = self._yaml().load(raw_config) or {}
        return config, raw_config

    def _save_config(self, config: dict[str, Any]) -> None:
        """Save config.yaml."""
        with open(CONFIG_PATH, "w", encoding="utf-8") as config_file:
            self._yaml().dump(config, config_file)

    @staticmethod
    def _camera_config_from_body(body: dict[str, Any]) -> dict[str, Any]:
        """Build ffmpeg camera config from request body."""
        camera_config: dict[str, Any] = {
            "name": body["name"].strip(),
            "host": body["host"].strip(),
            "port": body["port"],
            "path": body["path"].strip(),
            "stream_format": body["stream_format"],
        }

        if username := _optional_trimmed_string(body["username"]):
            camera_config["username"] = username
        if password := _optional_trimmed_string(body["password"]):
            camera_config["password"] = password

        if substream_path := _optional_trimmed_string(body["substream_path"]):
            camera_config["substream"] = {
                "path": substream_path,
                "port": body["substream_port"],
                "stream_format": body["substream_stream_format"],
            }

        if body["enable_recorder"]:
            camera_config["recorder"] = {"idle_timeout": body["idle_timeout"]}

        return camera_config

    def _add_camera_to_config(self, config: dict[str, Any]) -> None:
        """Add camera to config."""
        identifier = self.json_body["identifier"].strip()
        config.setdefault("ffmpeg", {})
        config["ffmpeg"].setdefault("camera", {})

        if identifier in config["ffmpeg"]["camera"]:
            raise ValueError(f"Camera '{identifier}' already exists")

        config["ffmpeg"]["camera"][identifier] = self._camera_config_from_body(
            self.json_body
        )

        if self.json_body["enable_nvr"]:
            config.setdefault("nvr", {})
            config["nvr"][identifier] = {}

    def _restore_config(self, raw_config: str) -> None:
        """Restore original config."""
        with open(CONFIG_PATH, "w", encoding="utf-8") as config_file:
            config_file.write(raw_config)

    async def post_camera_config(self) -> None:
        """Add a camera to config.yaml."""

        def _update_config() -> dict[str, Any]:
            config, raw_config = self._load_raw_config()
            self._add_camera_to_config(config)
            self._save_config(config)

            if not self.json_body["reload"]:
                return {"message": "Camera configuration saved", "reloaded": False}

            result = reload_config(self._vis)
            if result.success:
                return {
                    "message": "Camera configuration saved and reloaded",
                    "reloaded": True,
                    "restart_required": result.restart_required,
                }

            self._restore_config(raw_config)
            reload_config(self._vis)
            errors = [error.message for error in result.errors]
            return {
                "message": "Camera configuration failed validation",
                "reloaded": False,
                "restored": True,
                "errors": errors,
            }

        try:
            result = await self.run_in_executor(_update_config)
        except ValueError as error:
            self.response_error(HTTPStatus.CONFLICT, reason=str(error))
            return
        except (OSError, YAMLError) as error:
            LOGGER.error("Failed to add camera configuration: %s", error, exc_info=True)
            self.response_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                reason=f"Failed to update configuration: {error}",
            )
            return

        if result.get("errors"):
            self.response_error(
                HTTPStatus.BAD_REQUEST,
                reason="; ".join(result["errors"]),
            )
            return

        await self.response_success(response=result)

    async def get_cameras_endpoint(self) -> None:
        """Return cameras."""
        await self.response_success(response=self._get_cameras())

    async def get_failed_cameras_endpoint(self) -> None:
        """Return failed cameras."""
        await self.response_success(response=self._get_failed_cameras())
