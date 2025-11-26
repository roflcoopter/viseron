"""Camera Tune API handler."""

import json
import logging
import os
from http import HTTPStatus
from typing import Any

import yaml

from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import Role
from viseron.const import CONFIG_PATH

LOGGER = logging.getLogger(__name__)

CODEPROJECTAI_MODELS = {
    "ipcam-animal": [
        "bird",
        "cat",
        "dog",
        "horse",
        "sheep",
        "cow",
        "bear",
        "deer",
        "rabbit",
        "raccoon",
        "fox",
        "skunk",
        "squirrel",
        "pig",
    ],
    "ipcam-dark": ["bicycle", "bus", "car", "cat", "dog", "motorcycle", "person"],
    "ipcam-general": [
        "person",
        "vehicle",
        # ipcam-dark :
        "bicycle",
        "bus",
        "car",
        "cat",
        "dog",
        "motorcycle",
    ],
    "ipcam-combined": [
        "person",
        "bicycle",
        "car",
        "motorcycle",
        "bus",
        "truck",
        "bird",
        "cat",
        "dog",
        "horse",
        "sheep",
        "cow",
        "bear",
        "deer",
        "rabbit",
        "raccoon",
        "fox",
        "skunk",
        "squirrel",
        "pig",
    ],
}

# DeepStack labels (but this is same with /detectors/models/darknet/coco.names ??)
DEEPSTACK_LABELS = [
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop_sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair dryer",
    "toothbrush",
]


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
        with open(CONFIG_PATH, encoding="utf-8") as config_file:
            return yaml.safe_load(config_file) or {}

    def _load_labels_from_file(self, file_path: str) -> list[str]:
        """Load labels from file."""
        try:
            if not os.path.exists(file_path):
                return []
            with open(file_path, encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except (OSError, IOError) as e:
            LOGGER.warning(f"Failed to load labels from {file_path}: {e}")
            return []

    def _get_available_labels(
        self, component_name: str, cam_config: dict[str, Any]
    ) -> list[str] | None:
        """Get available labels for an object detector component."""
        if component_name == "darknet":
            return self._load_labels_from_file("/detectors/models/darknet/coco.names")
        if component_name == "hailo":
            return self._load_labels_from_file("/detectors/models/darknet/coco.names")
        if component_name == "edgetpu":
            return self._load_labels_from_file("/detectors/models/edgetpu/labels.txt")
        if component_name == "deepstack":
            return DEEPSTACK_LABELS
        if component_name == "codeprojectai":
            # Get custom_model from config, default to ipcam-general
            custom_model = cam_config.get("custom_model", "ipcam-general")
            if custom_model is None:
                custom_model = "ipcam-general"
            return CODEPROJECTAI_MODELS.get(custom_model, [])
        return None

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
                        available_labels = self._get_available_labels(
                            component_name, config_to_store
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

            # Handle components with direct cameras key
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

    def _merge_labels(
        self, existing_labels: list[dict[str, Any]], new_labels: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Merge labels, only keeping labels present in the request."""
        # Create a dict mapping label name to its config from existing labels
        existing_label_map = {}
        for label in existing_labels:
            label_name = label.get("label")
            if label_name:
                existing_label_map[label_name] = dict(label)

        # Build result with only labels from request
        result_labels = []
        for new_label in new_labels:
            label_name = new_label.get("label")
            if not label_name:
                continue

            if label_name in existing_label_map:
                # Merge with existing label to preserve other keys
                existing_label = existing_label_map[label_name]
                existing_label.update(new_label)
                result_labels.append(existing_label)
            else:
                # Add new label
                result_labels.append(dict(new_label))

        return result_labels

    def _merge_zones(
        self, existing_zones: list[dict[str, Any]], new_zones: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Merge zones, only keeping zones present in the request."""
        # Create a dict mapping zone name to its config from existing zones
        existing_zone_map = {}
        for zone in existing_zones:
            zone_name = zone.get("name")
            if zone_name:
                existing_zone_map[zone_name] = dict(zone)

        # Build result with only zones from request
        result_zones = []
        for new_zone in new_zones:
            zone_name = new_zone.get("name")
            if not zone_name:
                continue

            if zone_name in existing_zone_map:
                # Merge with existing zone to preserve other keys
                existing_zone = existing_zone_map[zone_name]
                self._merge_zone_data(existing_zone, new_zone)
                result_zones.append(existing_zone)
            else:
                # Add new zone
                result_zones.append(dict(new_zone))

        return result_zones

    def _merge_zone_data(
        self, existing_zone: dict[str, Any], new_zone: dict[str, Any]
    ) -> None:
        """Merge new zone data into existing zone."""
        # Special handling for nested labels in zones
        if "labels" in new_zone and "labels" in existing_zone:
            existing_zone["labels"] = self._merge_labels(
                existing_zone["labels"], new_zone["labels"]
            )
            # Update other keys except labels
            for key, value in new_zone.items():
                if key != "labels":
                    existing_zone[key] = value
        else:
            existing_zone.update(new_zone)

    def _update_object_detector_config(
        self,
        config: dict[str, Any],
        camera_id: str,
        component: str,
        data: dict[str, Any],
    ) -> bool:
        """Update object detector configuration in config dict."""
        # Find component config
        if component not in config:
            LOGGER.warning(f"Component '{component}' not found in config")
            return False

        component_config = config[component]
        if "object_detector" not in component_config:
            LOGGER.warning(
                f"object_detector domain not found in component '{component}'"
            )
            return False

        detector_config = component_config["object_detector"]
        if "cameras" not in detector_config:
            LOGGER.warning(f"cameras not found in {component}.object_detector config")
            return False

        cameras = detector_config["cameras"]
        if camera_id not in cameras:
            LOGGER.warning(
                f"Camera '{camera_id}' not found in {component}.object_detector"
            )
            return False

        camera_config = cameras[camera_id]

        # Update labels with merge strategy
        if "labels" in data:
            existing_labels = camera_config.get("labels", [])
            merged_labels = self._merge_labels(existing_labels, data["labels"])
            if merged_labels:
                camera_config["labels"] = merged_labels
            elif "labels" in camera_config:
                del camera_config["labels"]

        # Update zones with merge strategy
        if "zones" in data:
            existing_zones = camera_config.get("zones", [])
            merged_zones = self._merge_zones(existing_zones, data["zones"])
            if merged_zones:
                camera_config["zones"] = merged_zones
            elif "zones" in camera_config:
                del camera_config["zones"]

        # Update mask (always replace)
        if "mask" in data:
            if data["mask"]:
                camera_config["mask"] = data["mask"]
            elif "mask" in camera_config:
                del camera_config["mask"]

        # Update all other fields (miscellaneous fields like fps, etc.)
        # Frontend should filter out internal fields before sending
        for key, value in data.items():
            if key not in {"labels", "zones", "mask"}:
                if value is not None:
                    camera_config[key] = value
                elif key in camera_config:
                    # Remove key if value is None (allows deletion)
                    del camera_config[key]

        return True

    def _update_motion_detector_config(
        self,
        config: dict[str, Any],
        camera_id: str,
        component: str,
        data: dict[str, Any],
    ) -> bool:
        """Update motion detector configuration in config dict."""
        # Find component config
        if component not in config:
            LOGGER.warning(f"Component '{component}' not found in config")
            return False

        component_config = config[component]
        if "motion_detector" not in component_config:
            LOGGER.warning(
                f"motion_detector domain not found in component '{component}'"
            )
            return False

        detector_config = component_config["motion_detector"]
        if "cameras" not in detector_config:
            LOGGER.warning(f"cameras not found in {component}.motion_detector config")
            return False

        cameras = detector_config["cameras"]
        if camera_id not in cameras:
            LOGGER.warning(
                f"Camera '{camera_id}' not found in {component}.motion_detector"
            )
            return False

        camera_config = cameras[camera_id]

        # Update mask (always replace)
        if "mask" in data:
            if data["mask"]:
                camera_config["mask"] = data["mask"]
            elif "mask" in camera_config:
                del camera_config["mask"]

        # Update all other fields (miscellaneous fields)
        # Frontend should filter out internal fields before sending
        for key, value in data.items():
            if key != "mask":
                if value is not None:
                    camera_config[key] = value
                elif key in camera_config:
                    # Remove key if value is None (allows deletion)
                    del camera_config[key]

        return True

    def _update_face_recognition_config(
        self,
        config: dict[str, Any],
        camera_id: str,
        component: str,
        data: dict[str, Any],
    ) -> bool:
        """Update face recognition configuration in config dict."""
        # Find component config
        if component not in config:
            LOGGER.warning(f"Component '{component}' not found in config")
            return False

        component_config = config[component]
        if "face_recognition" not in component_config:
            LOGGER.warning(
                f"face_recognition domain not found in component '{component}'"
            )
            return False

        face_recognition_config = component_config["face_recognition"]
        if "cameras" not in face_recognition_config:
            LOGGER.warning(f"cameras not found in {component}.face_recognition config")
            return False

        cameras = face_recognition_config["cameras"]
        if camera_id not in cameras:
            LOGGER.warning(
                f"Camera '{camera_id}' not found in {component}.face_recognition"
            )
            return False

        camera_config = cameras[camera_id]

        # Initialize camera_config if it's None (e.g., when YAML has "camera_id: null")
        if camera_config is None:
            camera_config = {}
            cameras[camera_id] = camera_config

        # Build ordered config with labels first, then mask, then other fields
        ordered_config = {}

        # Update labels (simple list of strings for face_recognition)
        if "labels" in data:
            if data["labels"]:
                ordered_config["labels"] = data["labels"]
            # If labels is empty/None, don't include it (will be deleted from existing)
        elif "labels" in camera_config:
            # Preserve existing labels if not in data
            ordered_config["labels"] = camera_config["labels"]

        # Update mask (always replace)
        if "mask" in data:
            if data["mask"]:
                ordered_config["mask"] = data["mask"]
            # If mask is empty/None, don't include it (will be deleted from existing)
        elif "mask" in camera_config:
            # Preserve existing mask if not in data
            ordered_config["mask"] = camera_config["mask"]

        # Update all other fields (miscellaneous fields like expire_after, etc.)
        # Frontend should filter out internal fields before sending
        for key, value in camera_config.items():
            if key not in {"labels", "mask"}:
                ordered_config[key] = value

        for key, value in data.items():
            if key not in {"labels", "mask"}:
                if value is not None:
                    ordered_config[key] = value

        # Replace camera_config with ordered version
        cameras[camera_id] = ordered_config

        return True

    def _update_license_plate_recognition_config(
        self,
        config: dict[str, Any],
        camera_id: str,
        component: str,
        data: dict[str, Any],
    ) -> bool:
        """Update license plate recognition configuration in config dict."""
        # Find component config
        if component not in config:
            LOGGER.warning(f"Component '{component}' not found in config")
            return False

        component_config = config[component]
        if "license_plate_recognition" not in component_config:
            LOGGER.warning(
                f"license_plate_recognition domain not found in component '{component}'"
            )
            return False

        license_plate_recognition_config = component_config["license_plate_recognition"]
        if "cameras" not in license_plate_recognition_config:
            LOGGER.warning(
                f"cameras not found in {component}.license_plate_recognition config"
            )
            return False

        cameras = license_plate_recognition_config["cameras"]
        if camera_id not in cameras:
            LOGGER.warning(
                f"Camera '{camera_id}' not found in "
                f"{component}.license_plate_recognition"
            )
            return False

        camera_config = cameras[camera_id]

        # Initialize camera_config if it's None (e.g., when YAML has "camera_id: null")
        if camera_config is None:
            camera_config = {}
            cameras[camera_id] = camera_config

        # Build ordered config with labels first, then mask, then other fields
        ordered_config = {}

        # Update labels (simple list of strings for license_plate_recognition)
        if "labels" in data:
            if data["labels"]:
                ordered_config["labels"] = data["labels"]
            # If labels is empty/None, don't include it (will be deleted from existing)
        elif "labels" in camera_config:
            # Preserve existing labels if not in data
            ordered_config["labels"] = camera_config["labels"]

        # Update mask (always replace)
        if "mask" in data:
            if data["mask"]:
                ordered_config["mask"] = data["mask"]
            # If mask is empty/None, don't include it (will be deleted from existing)
        elif "mask" in camera_config:
            # Preserve existing mask if not in data
            ordered_config["mask"] = camera_config["mask"]

        # Update all other fields (miscellaneous fields)
        # Frontend should filter out internal fields before sending
        for key, value in camera_config.items():
            if key not in {"labels", "mask"}:
                ordered_config[key] = value

        for key, value in data.items():
            if key not in {"labels", "mask"}:
                if value is not None:
                    ordered_config[key] = value

        # Replace camera_config with ordered version
        cameras[camera_id] = ordered_config

        return True

    def _update_camera_config(
        self,
        config: dict[str, Any],
        camera_id: str,
        component: str,
        data: dict[str, Any],
    ) -> bool:
        """Update camera configuration in config dict."""
        # Find component config
        if component not in config:
            LOGGER.warning(f"Component '{component}' not found in config")
            return False

        component_config = config[component]
        if "camera" not in component_config:
            LOGGER.warning(f"camera domain not found in component '{component}'")
            return False

        camera_domain = component_config["camera"]
        if camera_id not in camera_domain:
            LOGGER.warning(f"Camera '{camera_id}' not found in {component}.camera")
            return False

        # Replace camera configuration entirely with data from request
        # Frontend should filter out internal fields before sending
        camera_domain[camera_id] = data

        return True

    def _save_config(self, config: dict[str, Any]) -> None:
        """Save config back to config.yaml."""
        with open(CONFIG_PATH, "w", encoding="utf-8") as config_file:
            yaml.dump(config, config_file, default_flow_style=False, sort_keys=False)

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
        # Parse JSON body manually
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

        # Support object_detector, motion_detector, face_recognition,
        # license_plate_recognition, and camera domains
        if domain not in [
            "object_detector",
            "motion_detector",
            "face_recognition",
            "license_plate_recognition",
            "camera",
        ]:
            self.response_error(
                status_code=HTTPStatus.BAD_REQUEST,
                reason=f"Domain '{domain}' update not supported. "
                "Only 'object_detector', 'motion_detector', 'face_recognition', "
                "'license_plate_recognition', and 'camera' are supported.",
            )
            return

        def _update_config() -> dict[str, Any]:
            config = self._load_config()

            if domain == "object_detector":
                success = self._update_object_detector_config(
                    config, camera_identifier, component, data
                )
            elif domain == "motion_detector":
                success = self._update_motion_detector_config(
                    config, camera_identifier, component, data
                )
            elif domain == "face_recognition":
                success = self._update_face_recognition_config(
                    config, camera_identifier, component, data
                )
            elif domain == "license_plate_recognition":
                success = self._update_license_plate_recognition_config(
                    config, camera_identifier, component, data
                )
            elif domain == "camera":
                success = self._update_camera_config(
                    config, camera_identifier, component, data
                )
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
        except (OSError, yaml.YAMLError) as e:
            LOGGER.error(f"Error updating camera tune: {e}", exc_info=True)
            self.response_error(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                reason=f"Failed to update configuration: {str(e)}",
            )
            return
