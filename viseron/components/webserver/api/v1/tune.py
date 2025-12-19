"""Camera Tune API handler."""

import json
import logging
from http import HTTPStatus
from typing import Any

from ruamel.yaml import YAML, YAMLError

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import Role
from viseron.const import CONFIG_PATH

from .tuning import (
    CameraTuningHandler,
    FaceRecognitionTuningHandler,
    LicensePlateRecognitionTuningHandler,
    MotionDetectorTuningHandler,
    ObjectDetectorTuningHandler,
)
from .tuning.labels import get_available_labels

LOGGER = logging.getLogger(__name__)


class TuneAPIHandler(BaseAPIHandler):
    """
    Handler for API calls related to camera tuning.

    Provides programmable access to get and update camera and all related domain
    configurations without leaving Viseron interface. Technically this will convert
    config.yaml settings to JSON and vice versa.

    Structure:
    {
        "camera_identifier": {
            "domain": {
                "component": {
                    "config_key": "config_value"
                }
            }
        }
    }
    """

    routes = [
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/tune",
            "supported_methods": ["GET"],
            "method": "get_all_camera_tune",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/tune/(?P<camera_identifier>[A-Za-z0-9_]+)",
            "supported_methods": ["GET"],
            "method": "get_camera_tune",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/tune/(?P<camera_identifier>[A-Za-z0-9_]+)",
            "supported_methods": ["PUT"],
            "method": "update_camera_tune",
        },
    ]

    def _load_config(self) -> dict[str, Any]:
        """Load and parse config.yaml."""
        yaml = YAML(typ="rt")  # round-trip mode, required to keep comments
        yaml.preserve_quotes = True

        with open(CONFIG_PATH, encoding="utf-8") as config_file:
            return yaml.load(config_file) or {}

    def _should_skip_camera(self, cam_id: str, camera_identifier: str | None) -> bool:
        """Check if camera should be skipped based on filter."""
        return camera_identifier is not None and cam_id != camera_identifier

    def _ensure_camera_in_settings(
        self, tune_settings: dict[str, Any], cam_id: str
    ) -> None:
        """Ensure camera entry exists in tune settings."""
        if cam_id not in tune_settings:
            tune_settings[cam_id] = {}

    def _ensure_domain_in_camera(
        self, tune_settings: dict[str, Any], cam_id: str, domain_name: str
    ) -> None:
        """Ensure domain entry exists for camera in tune settings."""
        if domain_name not in tune_settings[cam_id]:
            tune_settings[cam_id][domain_name] = {}

    def _process_direct_cameras(
        self,
        tune_settings: dict[str, Any],
        component_config: dict[str, Any],
        component_name: str,
        camera_identifier: str | None,
    ) -> None:
        """Process components with direct cameras key."""
        for cam_id, cam_config in component_config["cameras"].items():
            if self._should_skip_camera(cam_id, camera_identifier):
                continue
            self._ensure_camera_in_settings(tune_settings, cam_id)
            tune_settings[cam_id][component_name] = cam_config

    def _process_camera_domain(
        self,
        tune_settings: dict[str, Any],
        domain_config: dict[str, Any],
        component_name: str,
        domain_name: str,
        camera_identifier: str | None,
    ) -> None:
        """Process camera domain configuration."""
        for cam_id, cam_config in domain_config.items():
            if self._should_skip_camera(cam_id, camera_identifier):
                continue
            self._ensure_camera_in_settings(tune_settings, cam_id)
            self._ensure_domain_in_camera(tune_settings, cam_id, domain_name)

            # Store camera config as-is (no available_labels for camera domain)
            tune_settings[cam_id][domain_name][component_name] = cam_config

    def _process_domain_config(
        self,
        tune_settings: dict[str, Any],
        domain_name: str,
        domain_config: Any,
        component_name: str,
        camera_identifier: str | None,
    ) -> None:
        """Process a single domain configuration."""
        if not isinstance(domain_config, dict):
            return

        # Handle domains with 'cameras' key (e.g., mog2.motion_detector.cameras)
        if "cameras" in domain_config:
            cameras = domain_config["cameras"]
            if isinstance(cameras, dict):
                for cam_id, cam_config in cameras.items():
                    if self._should_skip_camera(cam_id, camera_identifier):
                        continue
                    self._ensure_camera_in_settings(tune_settings, cam_id)
                    self._ensure_domain_in_camera(tune_settings, cam_id, domain_name)

                    # Add available_labels for object_detector domain
                    config_to_store = cam_config if isinstance(cam_config, dict) else {}
                    if domain_name == "object_detector":
                        available_labels = get_available_labels(
                            component_name, domain_config
                        )
                        if available_labels:
                            config_to_store = (
                                dict(config_to_store) if config_to_store else {}
                            )
                            config_to_store["available_labels"] = available_labels
                    elif domain_name == "face_recognition":
                        # For face_recognition, available_labels is list of known faces
                        # from filesystem. This will be populated by backend based on
                        # face_recognition_path
                        pass

                    tune_settings[cam_id][domain_name][component_name] = config_to_store
            return

        # Skip if domain_config is empty or contains non-camera configs
        if not domain_config:
            return

        # Check if all values are dict or list (potential camera configs)
        # and skip if any value is a primitive type or list (non-camera config)
        values = list(domain_config.values())
        if not values:
            return

        # Skip if contains list values (like storage.recorder.tiers which is a list)
        # or if all values are primitives (string, int, bool, etc.)
        has_camera_like_structure = all(
            isinstance(value, dict)
            or (
                isinstance(value, list) and len(value) > 0 and isinstance(value[0], str)
            )
            for value in values
        )

        if has_camera_like_structure:
            for cam_id, cam_config in domain_config.items():
                if self._should_skip_camera(cam_id, camera_identifier):
                    continue
                self._ensure_camera_in_settings(tune_settings, cam_id)
                self._ensure_domain_in_camera(tune_settings, cam_id, domain_name)
                tune_settings[cam_id][domain_name][component_name] = cam_config

    def _transform_to_tune_structure(
        self, config: dict[str, Any], camera_identifier: str | None = None
    ) -> dict[str, Any]:
        """
        Transform config.yaml structure to tune API structure.

        From: {component: {domain: {cameras: {camera_id: {...}}}}}
        To: {camera_id: {domain: {component: {...}}}}
        """
        tune_settings: dict[str, Any] = {}

        for component_name, component_config in config.items():
            if not isinstance(component_config, dict):
                continue

            # Skip NVR component
            if component_name == "nvr":
                continue

            # Handle components with direct 'cameras' key
            if "cameras" in component_config and isinstance(
                component_config["cameras"], dict
            ):
                self._process_direct_cameras(
                    tune_settings, component_config, component_name, camera_identifier
                )
                continue

            # Process each domain in component config
            for domain_name, domain_config in component_config.items():
                self._process_domain_config(
                    tune_settings,
                    domain_name,
                    domain_config,
                    component_name,
                    camera_identifier,
                )

        return tune_settings

    def _save_config(self, config: dict[str, Any]) -> None:
        """Save config back to config.yaml."""

        yaml = YAML(typ="rt")  # round-trip mode, required to keep comments
        yaml.preserve_quotes = True

        with open(CONFIG_PATH, "w", encoding="utf-8") as config_file:
            yaml.dump(config, config_file)

    async def get_all_camera_tune(self) -> None:
        """Return all camera tune settings."""

        def _load_and_transform() -> dict[str, Any]:
            config = self._load_config()
            return self._transform_to_tune_structure(config)

        tune_settings = await self.run_in_executor(_load_and_transform)
        await self.response_success(response=tune_settings)

    async def get_camera_tune(self, camera_identifier: str) -> None:
        """Return camera tune settings for specific camera."""

        def _load_and_transform() -> dict[str, Any]:
            config = self._load_config()
            tune_settings = self._transform_to_tune_structure(config, camera_identifier)
            return tune_settings.get(camera_identifier, {})

        camera_tune_settings = await self.run_in_executor(_load_and_transform)

        if not camera_tune_settings:
            self.response_error(
                status_code=HTTPStatus.NOT_FOUND,
                reason=f"Camera '{camera_identifier}' not found.",
            )
            return

        await self.response_success(response=camera_tune_settings)

    async def update_camera_tune(self, camera_identifier: str) -> None:
        """Update camera tune settings."""

        try:
            request_data = json.loads(self.request.body)
        except json.JSONDecodeError as e:
            self.response_error(
                status_code=HTTPStatus.BAD_REQUEST,
                reason=f"Invalid JSON in request body: {str(e)}",
            )
            return

        domain = request_data.get("domain")
        component = request_data.get("component")
        data = request_data.get("data", {})

        # Validate request
        if not domain or not component:
            self.response_error(
                status_code=HTTPStatus.BAD_REQUEST,
                reason="Missing 'domain' or 'component' in request",
            )
            return

        if domain not in [
            "camera",
            "object_detector",
            "motion_detector",
            "face_recognition",
            "license_plate_recognition",
        ]:
            self.response_error(
                status_code=HTTPStatus.BAD_REQUEST,
                reason=f"Domain '{domain}' update not supported. "
                "Only 'camera', 'object_detector', 'motion_detector', "
                "'face_recognition', and 'license_plate_recognition' are supported.",
            )
            return

        def _update_config() -> dict[str, Any]:
            config = self._load_config()

            # Create appropriate handler based on domain
            handler: (
                ObjectDetectorTuningHandler
                | MotionDetectorTuningHandler
                | FaceRecognitionTuningHandler
                | LicensePlateRecognitionTuningHandler
                | CameraTuningHandler
                | None
            ) = None

            if domain == "camera":
                handler = CameraTuningHandler(config)
            elif domain == "object_detector":
                handler = ObjectDetectorTuningHandler(config)
            elif domain == "motion_detector":
                handler = MotionDetectorTuningHandler(config)
            elif domain == "face_recognition":
                handler = FaceRecognitionTuningHandler(config)
            elif domain == "license_plate_recognition":
                handler = LicensePlateRecognitionTuningHandler(config)

            if handler:
                success = handler.update(camera_identifier, component, data)
            else:
                success = False

            if success:
                self._save_config(config)
            return {"success": success}

        try:
            result = await self.run_in_executor(_update_config)
            if result["success"]:
                await self.response_success(
                    response={"message": "Configuration updated successfully"}
                )
            else:
                self.response_error(
                    status_code=HTTPStatus.NOT_FOUND,
                    reason=f"Failed to update configuration for camera "
                    f"'{camera_identifier}' in {component}.{domain}",
                )
                return
        except (OSError, YAMLError) as e:
            LOGGER.error(f"Error updating camera tune: {e}", exc_info=True)
            self.response_error(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                reason=f"Failed to update configuration: {str(e)}",
            )
            return
