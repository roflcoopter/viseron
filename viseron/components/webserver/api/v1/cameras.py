"""Cameras API Handler."""
from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

import voluptuous as vol
from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import Role
from viseron.const import CONFIG_PATH
from viseron.reload import reload_config

LOGGER = logging.getLogger(__name__)


CAMERA_IDENTIFIER_SCHEMA = vol.All(str, vol.Match(r"^[A-Za-z0-9_]+$"))
STREAM_FORMATS = ["rtsp", "mjpeg"]

CAMERA_CONFIG_BODY_SCHEMA = {
    vol.Required("name"): vol.All(str, vol.Length(min=1)),
    vol.Required("host"): vol.All(str, vol.Length(min=1)),
    vol.Optional("port", default=554): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=65535)
    ),
    vol.Required("path"): vol.All(str, vol.Length(min=1)),
    vol.Optional("stream_format", default="rtsp"): vol.In(STREAM_FORMATS),
    vol.Optional("username", default=None): vol.Maybe(str),
    vol.Optional("password", default=None): vol.Maybe(str),
    vol.Optional("substream_path", default=None): vol.Maybe(str),
    vol.Optional("substream_port", default=554): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=65535)
    ),
    vol.Optional("substream_stream_format", default="rtsp"): vol.In(STREAM_FORMATS),
    vol.Optional("fps", default=None): vol.Maybe(
        vol.All(vol.Coerce(int), vol.Range(min=1))
    ),
    vol.Optional("idle_timeout", default=5): vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Optional("enable_recorder", default=True): bool,
    vol.Optional("enable_nvr", default=True): bool,
    vol.Optional("record_only", default=False): bool,
    vol.Optional("width", default=None): vol.Maybe(
        vol.All(vol.Coerce(int), vol.Range(min=1))
    ),
    vol.Optional("height", default=None): vol.Maybe(
        vol.All(vol.Coerce(int), vol.Range(min=1))
    ),
    vol.Optional("video_filters", default=[]): [str],
    vol.Optional("reload", default=True): bool,
}


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
                    **CAMERA_CONFIG_BODY_SCHEMA,
                }
            ),
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/cameras/(?P<camera_identifier>[A-Za-z0-9_]+)/config",
            "supported_methods": ["GET"],
            "method": "get_camera_config",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/cameras/(?P<camera_identifier>[A-Za-z0-9_]+)/config",
            "supported_methods": ["PUT"],
            "method": "update_camera_config",
            "json_body_schema": vol.Schema(CAMERA_CONFIG_BODY_SCHEMA),
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/cameras/(?P<camera_identifier>[A-Za-z0-9_]+)",
            "supported_methods": ["DELETE"],
            "method": "delete_camera_config",
            "json_body_schema": vol.Schema(
                {vol.Optional("reload", default=True): bool}
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
    def _camera_config_from_body(
        body: dict[str, Any],
        existing_camera_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build ffmpeg camera config from request body."""
        camera_config: dict[str, Any] = CommentedMap(existing_camera_config or {})
        camera_config["name"] = body["name"].strip()
        camera_config["host"] = body["host"].strip()
        camera_config["port"] = body["port"]
        camera_config["path"] = body["path"].strip()
        camera_config["stream_format"] = body["stream_format"]

        if username := _optional_trimmed_string(body["username"]):
            camera_config["username"] = username
        else:
            camera_config.pop("username", None)

        if password := _optional_trimmed_string(body["password"]):
            camera_config["password"] = password
        elif existing_camera_config and "password" in existing_camera_config:
            camera_config["password"] = existing_camera_config["password"]
        else:
            camera_config.pop("password", None)

        if substream_path := _optional_trimmed_string(body["substream_path"]):
            camera_config["substream"] = {
                "path": substream_path,
                "port": body["substream_port"],
                "stream_format": body["substream_stream_format"],
            }
        else:
            camera_config.pop("substream", None)

        if body["fps"] is not None:
            camera_config["fps"] = body["fps"]
        else:
            camera_config.pop("fps", None)

        if body["enable_recorder"]:
            recorder_config = CommentedMap(camera_config.get("recorder") or {})
            recorder_config["idle_timeout"] = body["idle_timeout"]
            camera_config["recorder"] = recorder_config
        else:
            camera_config.pop("recorder", None)

        if body["record_only"]:
            camera_config["record_only"] = True
        else:
            camera_config.pop("record_only", None)

        if body["width"] is not None:
            camera_config["width"] = body["width"]
        else:
            camera_config.pop("width", None)

        if body["height"] is not None:
            camera_config["height"] = body["height"]
        else:
            camera_config.pop("height", None)

        video_filters = [
            video_filter.strip()
            for video_filter in body["video_filters"]
            if video_filter.strip()
        ]
        if video_filters:
            camera_config["video_filters"] = CommentedSeq(video_filters)
        else:
            camera_config.pop("video_filters", None)

        return camera_config

    @staticmethod
    def _camera_config_to_response(
        camera_identifier: str,
        camera_config: dict[str, Any],
        nvr_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Transform config.yaml camera data into API response."""
        substream = camera_config.get("substream") or {}
        recorder = camera_config.get("recorder") or {}
        return {
            "identifier": camera_identifier,
            "name": str(camera_config.get("name") or camera_identifier),
            "host": str(camera_config.get("host") or ""),
            "port": int(camera_config.get("port") or 554),
            "path": str(camera_config.get("path") or ""),
            "stream_format": str(camera_config.get("stream_format") or "rtsp"),
            "username": str(camera_config.get("username") or ""),
            "password": "",
            "password_set": "password" in camera_config,
            "substream_path": str(substream.get("path") or ""),
            "substream_port": int(substream.get("port") or 554),
            "substream_stream_format": str(
                substream.get("stream_format") or "rtsp"
            ),
            "fps": camera_config.get("fps"),
            "idle_timeout": int(recorder.get("idle_timeout") or 5),
            "enable_recorder": bool(recorder),
            "enable_nvr": camera_identifier in nvr_config,
            "record_only": bool(camera_config.get("record_only", False)),
            "width": camera_config.get("width"),
            "height": camera_config.get("height"),
            "video_filters": list(camera_config.get("video_filters") or []),
            "reload": True,
        }

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

    @staticmethod
    def _remove_camera_from_access_config(
        config: dict[str, Any], camera_identifier: str
    ) -> None:
        """Remove camera from camera access config."""
        auth_config = (config.get("webserver") or {}).get("auth") or {}
        for camera_group in (auth_config.get("camera_groups") or {}).values():
            if "cameras" in camera_group:
                camera_group["cameras"] = [
                    identifier
                    for identifier in camera_group["cameras"]
                    if identifier != camera_identifier
                ]
        for rule in auth_config.get("ldap_camera_access") or []:
            if "cameras" in rule:
                rule["cameras"] = [
                    identifier
                    for identifier in rule["cameras"]
                    if identifier != camera_identifier
                ]

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

    async def get_camera_config(self, camera_identifier: str) -> None:
        """Return camera config from config.yaml."""

        def _get_config() -> dict[str, Any]:
            config, _raw_config = self._load_raw_config()
            camera_config = (
                config.get("ffmpeg", {}).get("camera", {}).get(camera_identifier)
            )
            if camera_config is None:
                raise ValueError(f"Camera '{camera_identifier}' not found")
            return self._camera_config_to_response(
                camera_identifier, camera_config, config.get("nvr") or {}
            )

        try:
            camera_config = await self.run_in_executor(_get_config)
        except ValueError as error:
            self.response_error(HTTPStatus.NOT_FOUND, reason=str(error))
            return
        except (OSError, YAMLError) as error:
            LOGGER.error("Failed to load camera configuration: %s", error, exc_info=True)
            self.response_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                reason=f"Failed to load configuration: {error}",
            )
            return

        await self.response_success(response={"config": camera_config})

    async def update_camera_config(self, camera_identifier: str) -> None:
        """Update camera config in config.yaml."""

        def _update_config() -> dict[str, Any]:
            config, raw_config = self._load_raw_config()
            cameras_config = config.get("ffmpeg", {}).get("camera", {})
            if camera_identifier not in cameras_config:
                raise ValueError(f"Camera '{camera_identifier}' not found")

            cameras_config[camera_identifier] = self._camera_config_from_body(
                self.json_body, cameras_config[camera_identifier]
            )

            if self.json_body["enable_nvr"]:
                config.setdefault("nvr", {})
                config["nvr"].setdefault(camera_identifier, {})
            else:
                (config.get("nvr") or {}).pop(camera_identifier, None)

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
            self.response_error(HTTPStatus.NOT_FOUND, reason=str(error))
            return
        except (OSError, YAMLError) as error:
            LOGGER.error(
                "Failed to update camera configuration: %s", error, exc_info=True
            )
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

    async def delete_camera_config(self, camera_identifier: str) -> None:
        """Delete camera from config.yaml."""

        def _delete_config() -> dict[str, Any]:
            config, raw_config = self._load_raw_config()
            cameras_config = config.get("ffmpeg", {}).get("camera", {})
            if camera_identifier not in cameras_config:
                raise ValueError(f"Camera '{camera_identifier}' not found")

            cameras_config.pop(camera_identifier)
            (config.get("nvr") or {}).pop(camera_identifier, None)
            self._remove_camera_from_access_config(config, camera_identifier)
            self._save_config(config)

            if not self.json_body["reload"]:
                return {"message": "Camera configuration deleted", "reloaded": False}

            result = reload_config(self._vis)
            if result.success:
                return {
                    "message": "Camera configuration deleted and reloaded",
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
            result = await self.run_in_executor(_delete_config)
        except ValueError as error:
            self.response_error(HTTPStatus.NOT_FOUND, reason=str(error))
            return
        except (OSError, YAMLError) as error:
            LOGGER.error(
                "Failed to delete camera configuration: %s", error, exc_info=True
            )
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
