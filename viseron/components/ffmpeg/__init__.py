"""FFmpeg component."""

import logging
import threading

import voluptuous as vol

from viseron import Viseron
from viseron.domains import setup_domain
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN

from .const import COMPONENT, CONFIG_CAMERAS

CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT: {
            vol.Required(CONFIG_CAMERAS): {str: object},
        },
    },
    extra=vol.ALLOW_EXTRA,
)

LOGGER = logging.getLogger(__name__)


def setup(vis: Viseron, config):
    """Set up the ffmpeg component."""
    config = config[COMPONENT]
    vis.data[COMPONENT] = {}

    setup_threads = []
    for camera_identifier, camera_config in config[CONFIG_CAMERAS].items():
        pruned_config = {}
        pruned_config[camera_identifier] = camera_config
        setup_threads.append(
            threading.Thread(
                target=setup_domain,
                args=(
                    vis,
                    pruned_config,
                    COMPONENT,
                    CAMERA_DOMAIN,
                ),
                daemon=True,
                name="ffmpeg_camera_setup",
            )
        )

    for thread in setup_threads:
        thread.start()
    for thread in setup_threads:
        thread.join()

    return True
