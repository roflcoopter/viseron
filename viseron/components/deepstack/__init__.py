"""DeepStack object detection."""
import logging

import voluptuous as vol

from viseron import Viseron
from viseron.domains import setup_domain
from viseron.domains.face_recognition import (
    BASE_CONFIG_SCHEMA as FACE_RECOGNITION_BASE_CONFIG_SCHEMA,
)
from viseron.domains.object_detector import (
    BASE_CONFIG_SCHEMA as OBJECT_DETECTOR_BASE_CONFIG_SCHEMA,
)

from .const import (
    COMPONENT,
    CONFIG_API_KEY,
    CONFIG_CUSTOM_MODEL,
    CONFIG_FACE_RECOGNITION,
    CONFIG_HOST,
    CONFIG_IMAGE_HEIGHT,
    CONFIG_IMAGE_WIDTH,
    CONFIG_MIN_CONFIDENCE,
    CONFIG_OBJECT_DETECTOR,
    CONFIG_PORT,
    CONFIG_TIMEOUT,
    CONFIG_TRAIN,
    DEFAULT_API_KEY,
    DEFAULT_CUSTOM_MODEL,
    DEFAULT_IMAGE_HEIGHT,
    DEFAULT_IMAGE_WIDTH,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_TIMEOUT,
    DEFAULT_TRAIN,
)

LOGGER = logging.getLogger(__name__)

OBJECT_DETECTOR_SCHEMA = OBJECT_DETECTOR_BASE_CONFIG_SCHEMA.extend(
    {
        vol.Optional(CONFIG_IMAGE_WIDTH, default=DEFAULT_IMAGE_WIDTH): vol.Maybe(int),
        vol.Optional(CONFIG_IMAGE_HEIGHT, default=DEFAULT_IMAGE_HEIGHT): vol.Maybe(int),
        vol.Optional(CONFIG_CUSTOM_MODEL, default=DEFAULT_CUSTOM_MODEL): vol.Maybe(str),
    }
)

FACE_RECOGNITION_SCHEMA = FACE_RECOGNITION_BASE_CONFIG_SCHEMA.extend(
    {
        vol.Optional(CONFIG_TRAIN, default=DEFAULT_TRAIN): bool,
        vol.Optional(CONFIG_MIN_CONFIDENCE, default=DEFAULT_MIN_CONFIDENCE): vol.All(
            vol.Any(0, 1, vol.All(float, vol.Range(min=0.0, max=1.0))),
            vol.Coerce(float),
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT: vol.Schema(
            {
                vol.Required(CONFIG_HOST): str,
                vol.Required(CONFIG_PORT): vol.All(int, vol.Range(min=1024, max=49151)),
                vol.Optional(CONFIG_API_KEY, default=DEFAULT_API_KEY): vol.Maybe(str),
                vol.Optional(CONFIG_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Maybe(int),
                vol.Optional(CONFIG_OBJECT_DETECTOR): OBJECT_DETECTOR_SCHEMA,
                vol.Optional(CONFIG_FACE_RECOGNITION): FACE_RECOGNITION_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config):
    """Set up the edgetpu component."""
    config = config[COMPONENT]
    if config.get(CONFIG_OBJECT_DETECTOR, None):
        setup_domain(vis, COMPONENT, CONFIG_OBJECT_DETECTOR, config)
    if config.get(CONFIG_FACE_RECOGNITION, None):
        setup_domain(vis, COMPONENT, CONFIG_FACE_RECOGNITION, config)

    return True
