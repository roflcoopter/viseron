"""Base tuning handler with common utilities."""

import logging
from typing import Any

from ruamel.yaml.comments import CommentedMap

from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.domains.object_detector.const import (
    CONFIG_LABEL_LABEL,
    CONFIG_LABELS,
    CONFIG_ZONE_NAME,
)
from viseron.domains.post_processor.const import CONFIG_CAMERAS

LOGGER = logging.getLogger(__name__)


class BaseTuningHandler:
    """Base class for domain-specific tuning handlers."""

    def __init__(self, config: dict[str, Any]):
        """Initialize the handler with config."""
        self.config = config

    def _preserve_yaml_tags(
        self, existing: Any, new_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Preserve YAML tags (like !secret) when updating configuration.

        If the new value is the same as the existing value's string representation,
        keep the existing value with its tag intact.
        """
        if not isinstance(existing, dict):
            return new_data

        # Create result dict, preserving CommentedMap if existing is one
        result: dict[str, Any] = (
            CommentedMap() if isinstance(existing, CommentedMap) else {}
        )

        # Process all keys from new_data
        for key, new_value in new_data.items():
            if key in existing:
                existing_value = existing[key]

                # Recursively handle nested dicts first
                if isinstance(new_value, dict) and isinstance(existing_value, dict):
                    result[key] = self._preserve_yaml_tags(existing_value, new_value)
                    continue

                # Recursively handle lists
                if isinstance(new_value, list) and isinstance(existing_value, list):
                    result[key] = self._preserve_yaml_tags_in_list(
                        existing_value, new_value
                    )
                    continue

                # Check if existing value has a tag (like !secret)
                # Only check after ensuring it's not a dict/list
                if (
                    hasattr(existing_value, "tag")
                    and hasattr(existing_value, "value")
                    and existing_value.tag is not None
                ):
                    # Check if the string representation matches
                    if str(existing_value.value) == str(new_value):
                        # Keep the tagged value
                        result[key] = existing_value
                        continue

            # Default: use new value
            result[key] = new_value

        return result

    def _preserve_yaml_tags_in_list(
        self, existing: list[Any], new_data: list[Any]
    ) -> list[Any]:
        """Preserve YAML tags in list items."""
        result = []
        for i, new_item in enumerate(new_data):
            if i < len(existing):
                existing_item = existing[i]
                if isinstance(new_item, dict) and isinstance(existing_item, dict):
                    result.append(self._preserve_yaml_tags(existing_item, new_item))
                else:
                    result.append(new_item)
            else:
                result.append(new_item)
        return result

    def _get_camera_config(
        self, camera_id: str, component: str, domain: str
    ) -> dict[str, Any] | None:
        """Get camera configuration for a specific domain."""
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
        if domain == CAMERA_DOMAIN:
            if camera_id not in domain_config:
                LOGGER.warning(
                    f"Camera '{camera_id}' not found in {component}.{domain}"
                )
                return None
            return domain_config[camera_id]

        # Other domains have 'cameras' key
        if CONFIG_CAMERAS not in domain_config:
            LOGGER.warning(f"cameras not found in {component}.{domain} config")
            return None

        cameras = domain_config[CONFIG_CAMERAS]
        if camera_id not in cameras:
            LOGGER.warning(f"Camera '{camera_id}' not found in {component}.{domain}")
            return None

        return cameras[camera_id]

    def _get_direct_camera_config(
        self, camera_id: str, component: str
    ) -> dict[str, Any] | None:
        """Get camera configuration for components with direct 'cameras' key."""
        if component not in self.config:
            LOGGER.warning(f"Component '{component}' not found in config")
            return None

        component_config = self.config[component]
        cameras = component_config.get(CONFIG_CAMERAS, {})

        if camera_id not in cameras:
            LOGGER.warning(f"Camera '{camera_id}' not found in {component}.cameras")
            return None

        return cameras[camera_id]

    def _merge_labels(
        self, existing_labels: list[dict[str, Any]], new_labels: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Merge labels, only keeping labels present in the request."""
        # Create a dict mapping label name to its config from existing labels
        existing_label_map = {}
        for label in existing_labels:
            label_name = label.get(CONFIG_LABEL_LABEL)
            if label_name:
                existing_label_map[label_name] = dict(label)

        # Build result with only labels from request
        result_labels = []
        for new_label in new_labels:
            label_name = new_label.get(CONFIG_LABEL_LABEL)
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
            zone_name = zone.get(CONFIG_ZONE_NAME)
            if zone_name:
                existing_zone_map[zone_name] = dict(zone)

        # Build result with only zones from request
        result_zones = []
        for new_zone in new_zones:
            zone_name = new_zone.get(CONFIG_ZONE_NAME)
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
        if CONFIG_LABELS in new_zone and CONFIG_LABELS in existing_zone:
            existing_zone[CONFIG_LABELS] = self._merge_labels(
                existing_zone[CONFIG_LABELS], new_zone[CONFIG_LABELS]
            )
            # Update other keys except labels
            for key, value in new_zone.items():
                if key != CONFIG_LABELS:
                    existing_zone[key] = value
        else:
            existing_zone.update(new_zone)

    def update(self, camera_id: str, component: str, data: dict[str, Any]) -> bool:
        """Update configuration. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement update method")
