"""DeepStack object detection."""
import logging

import voluptuous as vol

from viseron import Viseron
from viseron.domains import setup_domain
from viseron.domains.object_detector import BASE_CONFIG_SCHEMA

from .const import (
    COMPONENT,
    CONFIG_API_KEY,
    CONFIG_CUSTOM_MODEL,
    CONFIG_HOST,
    CONFIG_IMAGE_HEIGHT,
    CONFIG_IMAGE_WIDTH,
    CONFIG_OBJECT_DETECTOR,
    CONFIG_PORT,
    CONFIG_TIMEOUT,
    DEFAULT_API_KEY,
    DEFAULT_CUSTOM_MODEL,
    DEFAULT_IMAGE_HEIGHT,
    DEFAULT_IMAGE_WIDTH,
    DEFAULT_TIMEOUT,
)

LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT: vol.Schema(
            {
                vol.Required(CONFIG_OBJECT_DETECTOR): BASE_CONFIG_SCHEMA.extend(
                    {
                        vol.Required(CONFIG_HOST): str,
                        vol.Required(CONFIG_PORT): vol.All(
                            int, vol.Range(min=1024, max=49151)
                        ),
                        vol.Optional(
                            CONFIG_IMAGE_WIDTH, default=DEFAULT_IMAGE_WIDTH
                        ): vol.Maybe(int),
                        vol.Optional(
                            CONFIG_IMAGE_HEIGHT, default=DEFAULT_IMAGE_HEIGHT
                        ): vol.Maybe(int),
                        vol.Optional(
                            CONFIG_CUSTOM_MODEL, default=DEFAULT_CUSTOM_MODEL
                        ): vol.Maybe(str),
                        vol.Optional(
                            CONFIG_API_KEY, default=DEFAULT_API_KEY
                        ): vol.Maybe(str),
                        vol.Optional(
                            CONFIG_TIMEOUT, default=DEFAULT_TIMEOUT
                        ): vol.Maybe(int),
                    }
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config):
    """Set up the edgetpu component."""
    config = config[COMPONENT]
    for domain in config.keys():
        setup_domain(vis, config, COMPONENT, domain)

    return True
