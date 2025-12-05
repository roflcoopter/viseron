"""Base tuning handler with common utilities."""

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


class BaseTuningHandler:
    """Base class for domain-specific tuning handlers."""

    def __init__(self, config: dict[str, Any]):
        """Initialize the handler with config."""
        self.config = config

    def _get_camera_config(
        self, camera_id: str, component: str, domain: str
    ) -> dict[str, Any] | None:
        """
        Get camera configuration for a specific domain.

        Args:
            camera_id: Camera identifier
            component: Component name (e.g., 'deepstack', 'edgetpu')
            domain: Domain name (e.g., 'object_detector', 'face_recognition')

        Returns:
            Camera config dict if found, None otherwise
        """
        # Find component config
        if component not in self.config:
            LOGGER.warning(f"Component '{component}' not found in config")
            return None

        component_config = self.config[component]
        if domain not in component_config:
            LOGGER.warning(f"{domain} domain not found in component '{component}'")
            return None

        domain_config = component_config[domain]

        # Special case for 'camera' domain which doesn't have 'cameras' key
        if domain == "camera":
            if camera_id not in domain_config:
                LOGGER.warning(
                    f"Camera '{camera_id}' not found in {component}.{domain}"
                )
                return None
            return domain_config[camera_id]

        # Other domains have 'cameras' key
        if "cameras" not in domain_config:
            LOGGER.warning(f"cameras not found in {component}.{domain} config")
            return None

        cameras = domain_config["cameras"]
        if camera_id not in cameras:
            LOGGER.warning(f"Camera '{camera_id}' not found in {component}.{domain}")
            return None

        return cameras[camera_id]

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

    def update(self, camera_id: str, component: str, data: dict[str, Any]) -> bool:
        """Update configuration. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement update method")
