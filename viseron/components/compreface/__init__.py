"""Compreface object detection."""
import logging

import voluptuous as vol

from viseron import Viseron
from viseron.components.compreface.face_recognition import ComprefaceTrain
from viseron.domains import RequireDomain, setup_domain
from viseron.domains.face_recognition import (
    BASE_CONFIG_SCHEMA as FACE_RECOGNITION_BASE_CONFIG_SCHEMA,
)
from viseron.domains.face_recognition.const import CONFIG_CAMERAS
from viseron.helpers.schemas import FLOAT_MIN_ZERO_MAX_ONE
from viseron.helpers.validators import Maybe

from .const import (
    COMPONENT,
    CONFIG_API_KEY,
    CONFIG_DET_PROB_THRESHOLD,
    CONFIG_FACE_PLUGINS,
    CONFIG_FACE_RECOGNITION,
    CONFIG_HOST,
    CONFIG_LIMIT,
    CONFIG_PORT,
    CONFIG_PREDICTION_COUNT,
    CONFIG_STATUS,
    CONFIG_TRAIN,
    DEFAULT_DET_PROB_THRESHOLD,
    DEFAULT_FACE_PLUGINS,
    DEFAULT_LIMIT,
    DEFAULT_PREDICTION_COUNT,
    DEFAULT_STATUS,
    DEFAULT_TRAIN,
    DESC_API_KEY,
    DESC_COMPONENT,
    DESC_DET_PROB_THRESHOLD,
    DESC_FACE_PLUGINS,
    DESC_FACE_RECOGNITION,
    DESC_HOST,
    DESC_LIMIT,
    DESC_PORT,
    DESC_PREDICTION_COUNT,
    DESC_STATUS,
    DESC_TRAIN,
)

LOGGER = logging.getLogger(__name__)

FACE_RECOGNITION_SCHEMA = FACE_RECOGNITION_BASE_CONFIG_SCHEMA.extend(
    {
        vol.Required(CONFIG_HOST, description=DESC_HOST): str,
        vol.Required(CONFIG_PORT, description=DESC_PORT): int,
        vol.Required(
            CONFIG_API_KEY,
            description=DESC_API_KEY,
        ): Maybe(str),
        vol.Optional(CONFIG_TRAIN, default=DEFAULT_TRAIN, description=DESC_TRAIN): bool,
        vol.Optional(
            CONFIG_DET_PROB_THRESHOLD,
            default=DEFAULT_DET_PROB_THRESHOLD,
            description=DESC_DET_PROB_THRESHOLD,
        ): FLOAT_MIN_ZERO_MAX_ONE,
        vol.Optional(CONFIG_LIMIT, default=DEFAULT_LIMIT, description=DESC_LIMIT): int,
        vol.Optional(
            CONFIG_PREDICTION_COUNT,
            default=DEFAULT_PREDICTION_COUNT,
            description=DESC_PREDICTION_COUNT,
        ): int,
        vol.Optional(
            CONFIG_FACE_PLUGINS,
            default=DEFAULT_FACE_PLUGINS,
            description=DESC_FACE_PLUGINS,
        ): Maybe(str),
        vol.Optional(
            CONFIG_STATUS, default=DEFAULT_STATUS, description=DESC_STATUS
        ): bool,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): vol.Schema(
            {
                vol.Optional(
                    CONFIG_FACE_RECOGNITION, description=DESC_FACE_RECOGNITION
                ): FACE_RECOGNITION_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config):
    """Set up the edgetpu component."""
    config = config[COMPONENT]

    if config.get(CONFIG_FACE_RECOGNITION, None):
        for camera_identifier in config[CONFIG_FACE_RECOGNITION][CONFIG_CAMERAS].keys():
            setup_domain(
                vis,
                COMPONENT,
                CONFIG_FACE_RECOGNITION,
                config,
                identifier=camera_identifier,
                require_domains=[
                    RequireDomain(
                        domain="camera",
                        identifier=camera_identifier,
                    )
                ],
            )

        if config[CONFIG_FACE_RECOGNITION][CONFIG_TRAIN]:
            ComprefaceTrain(config)

    return True
