"""ONVIF tuning handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from viseron.components.onvif.const import (
    COMPONENT as ONVIF_COMPONENT,
    CONFIG_CLIENT,
    CONFIG_DEVICE,
    CONFIG_HOST,
    CONFIG_IMAGING,
    CONFIG_MEDIA,
    CONFIG_ONVIF_AUTO_CONFIG,
    CONFIG_ONVIF_PASSWORD,
    CONFIG_ONVIF_PORT,
    CONFIG_ONVIF_TIMEOUT,
    CONFIG_ONVIF_USE_HTTPS,
    CONFIG_ONVIF_USERNAME,
    CONFIG_ONVIF_VERIFY_SSL,
    CONFIG_ONVIF_WSDL_DIR,
    CONFIG_PTZ,
    DEFAULT_ONVIF_AUTO_CONFIG,
)

from .base import BaseTuningHandler

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)

# ONVIF client configuration keys that should be grouped under "client"
ONVIF_CLIENT_KEYS = [
    CONFIG_HOST,
    CONFIG_ONVIF_PORT,
    CONFIG_ONVIF_USERNAME,
    CONFIG_ONVIF_PASSWORD,
    CONFIG_ONVIF_TIMEOUT,
    CONFIG_ONVIF_USE_HTTPS,
    CONFIG_ONVIF_VERIFY_SSL,
    CONFIG_ONVIF_WSDL_DIR,
    CONFIG_ONVIF_AUTO_CONFIG,
]

ONVIF_SERVICES = [
    CONFIG_DEVICE,
    CONFIG_IMAGING,
    CONFIG_MEDIA,
    CONFIG_PTZ,
]

# Mapping from service config key to ONVIF service getter method name
SERVICE_GETTER_MAP = {
    CONFIG_DEVICE: "get_device_service",
    CONFIG_MEDIA: "get_media_service",
    CONFIG_IMAGING: "get_imaging_service",
    CONFIG_PTZ: "get_ptz_service",
}


def get_available_services(vis: Viseron, camera_identifier: str) -> list[str]:
    """Get list of available ONVIF services for a camera."""
    available_services: list[str] = []

    onvif_component = vis.data.get(ONVIF_COMPONENT)
    if onvif_component is None:
        return available_services

    for service, getter_name in SERVICE_GETTER_MAP.items():
        getter = getattr(onvif_component, getter_name, None)
        if getter and getter(camera_identifier) is not None:
            available_services.append(service)

    return available_services


def process_onvif_config(
    vis: Viseron, cam_config: dict[str, Any], camera_identifier: str
) -> dict[str, Any]:
    """Process ONVIF config to group base keys under 'client' key.

    If auto_config is True, all available ONVIF_SERVICES will be empty dicts (ignored).
    If auto_config is False, all available ONVIF_SERVICES will be included with their
    existing values or as empty dicts if they don't exist.

    Only services that are actually available for the camera will be included.
    """
    client_config: dict[str, Any] = {}
    other_config: dict[str, Any] = {}

    for key, value in cam_config.items():
        if key in ONVIF_CLIENT_KEYS:
            client_config[key] = value
        else:
            other_config[key] = value

    # Build result with client first
    result: dict[str, Any] = {}

    # Ensure auto_config is always present in client config
    if CONFIG_ONVIF_AUTO_CONFIG not in client_config:
        client_config[CONFIG_ONVIF_AUTO_CONFIG] = DEFAULT_ONVIF_AUTO_CONFIG

    if client_config:
        result[CONFIG_CLIENT] = client_config

    # Get available services for this camera
    available_services = get_available_services(vis, camera_identifier)

    auto_config = client_config.get(CONFIG_ONVIF_AUTO_CONFIG, DEFAULT_ONVIF_AUTO_CONFIG)
    if auto_config:
        # If auto_config is True, all available services are empty dicts (ignored)
        for service in available_services:
            result[service] = {}
    else:
        # If auto_config is False, include all available services with existing values
        # or as empty dicts if they don't exist
        for service in available_services:
            result[service] = other_config.get(service, {})

    return result


class OnvifTuningHandler(BaseTuningHandler):
    """Handler for ONVIF configuration updates."""

    def _reorder_onvif_config(self, onvif_config: dict[str, Any]) -> None:
        """Reorder ONVIF config keys: client keys first, then service keys.

        This ensures the YAML output has client settings (port, username, etc.)
        at the top, followed by service configurations (ptz, imaging, etc.).
        """
        # Collect all current keys and values
        client_items: list[tuple[str, Any]] = []
        service_items: list[tuple[str, Any]] = []
        other_items: list[tuple[str, Any]] = []

        for key in list(onvif_config.keys()):
            value = onvif_config[key]
            if key in ONVIF_CLIENT_KEYS:
                client_items.append((key, value))
            elif key in ONVIF_SERVICES:
                service_items.append((key, value))
            else:
                other_items.append((key, value))

        # Clear and rebuild in correct order
        onvif_config.clear()

        # Add client keys first (in defined order)
        for key in ONVIF_CLIENT_KEYS:
            for item_key, item_value in client_items:
                if item_key == key:
                    onvif_config[key] = item_value
                    break

        # Add any other non-service keys
        for key, value in other_items:
            onvif_config[key] = value

        # Add service keys last (in defined order)
        for key in ONVIF_SERVICES:
            for item_key, item_value in service_items:
                if item_key == key:
                    onvif_config[key] = item_value
                    break

    def update(self, camera_id: str, component: str, data: dict[str, Any]) -> bool:
        """Update ONVIF configuration.

        For 'client' component: updates base ONVIF settings (port, username, etc.)
        For service components: only updates if auto_config is False
        """
        onvif_config = self._get_direct_camera_config(camera_id, ONVIF_COMPONENT)
        if onvif_config is None:
            return False

        # 'component' parameter is the section (client, ptz, imaging, etc.)
        section = component

        if not section:
            LOGGER.warning("Missing 'component' in update data")
            return False

        if section == CONFIG_CLIENT:
            # Update client config - keys go directly under camera config
            # (no 'client' wrapper)
            for key, value in data.items():
                if key in ONVIF_CLIENT_KEYS:
                    onvif_config[key] = value

            # Reorder keys: client keys first, then service keys
            self._reorder_onvif_config(onvif_config)
            return True

        if section in ONVIF_SERVICES:
            # Check if auto_config is False before allowing service updates
            auto_config = onvif_config.get(
                CONFIG_ONVIF_AUTO_CONFIG, DEFAULT_ONVIF_AUTO_CONFIG
            )
            if auto_config:
                LOGGER.warning(
                    f"Cannot update service '{section}' when auto_config is True"
                )
                return False

            # Update service config
            updated_config = self._preserve_yaml_tags(
                onvif_config.get(section, {}), data
            )
            onvif_config[section] = updated_config
            return True

        LOGGER.warning(f"Unknown component '{section}' for ONVIF update")
        return False
