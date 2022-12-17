"""GStreamer component."""

import logging

import voluptuous as vol

from viseron import Viseron
from viseron.domains import setup_domain
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN

from .const import COMPONENT, CONFIG_CAMERA, DESC_CAMERA, DESC_COMPONENT

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): {
            vol.Required(CONFIG_CAMERA, description=DESC_CAMERA): {str: object},
        },
    },
    extra=vol.ALLOW_EXTRA,
)

LOGGER = logging.getLogger(__name__)


def setup(vis: Viseron, config):
    """Set up the gstreamer component."""
    config = config[COMPONENT]
    vis.data[COMPONENT] = {}

    for camera_identifier, camera_config in config[CONFIG_CAMERA].items():
        pruned_config = {}
        pruned_config[camera_identifier] = camera_config
        setup_domain(
            vis, COMPONENT, CAMERA_DOMAIN, pruned_config, identifier=camera_identifier
        )

    return True
