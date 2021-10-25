"""FFmpeg component."""

import logging

import voluptuous as vol

from viseron import Viseron
from viseron.domains import setup_domain
from viseron.domains.camera import DOMAIN as CAMERA_DOMAIN

from .const import COMPONENT

CONFIG_CAMERAS = "cameras"

CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT: {
            vol.Required(CONFIG_CAMERAS): [{vol.Extra: object}],
        },
    },
    extra=vol.ALLOW_EXTRA,
)

LOGGER = logging.getLogger(__name__)


def setup(vis: Viseron, config):
    """Set up the ffmpeg component."""
    config = config[COMPONENT]
    vis.data[COMPONENT] = {}

    LOGGER.debug(config)
    for camera_config in config[CONFIG_CAMERAS]:
        setup_domain(vis, camera_config, COMPONENT, CAMERA_DOMAIN)

    return True
