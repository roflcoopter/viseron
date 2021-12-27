"""DeepStack object detection."""
import logging
import os

import voluptuous as vol

from viseron import Viseron
from viseron.const import ENV_CUDA_SUPPORTED
from viseron.domains import setup_domain
from viseron.domains.face_recognition import (
    BASE_CONFIG_SCHEMA as FACE_RECOGNITION_BASE_CONFIG_SCHEMA,
)

from .const import COMPONENT, CONFIG_FACE_RECOGNITION, CONFIG_MODEL, SUPPORTED_MODELS

LOGGER = logging.getLogger(__name__)


def get_default_model() -> str:
    """Return default model."""
    if os.getenv(ENV_CUDA_SUPPORTED) == "true":
        return "cnn"
    return "hog"


FACE_RECOGNITION_SCHEMA = FACE_RECOGNITION_BASE_CONFIG_SCHEMA.extend(
    {
        vol.Optional(CONFIG_MODEL, default=get_default_model()): vol.In(
            SUPPORTED_MODELS
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT: vol.Schema(
            {
                vol.Optional(CONFIG_FACE_RECOGNITION): FACE_RECOGNITION_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config):
    """Set up the edgetpu component."""
    config = config[COMPONENT]
    if config.get(CONFIG_FACE_RECOGNITION, None):
        setup_domain(vis, config, COMPONENT, CONFIG_FACE_RECOGNITION)

    return True
