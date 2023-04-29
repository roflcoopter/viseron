"""CodeProject.AI component."""
import logging

import voluptuous as vol

from viseron import Viseron
from viseron.components.codeprojectai.face_recognition import CodeProjectAITrain
from viseron.domains import OptionalDomain, RequireDomain, setup_domain
from viseron.domains.face_recognition import (
    BASE_CONFIG_SCHEMA as FACE_RECOGNITION_BASE_CONFIG_SCHEMA,
)
from viseron.domains.license_plate_recognition import (
    BASE_CONFIG_SCHEMA as LICENSE_PLATE_RECOGNITION_SCHEMA,
)
from viseron.domains.motion_detector.const import DOMAIN as MOTION_DETECTOR_DOMAIN
from viseron.domains.object_detector import (
    BASE_CONFIG_SCHEMA as OBJECT_DETECTOR_BASE_CONFIG_SCHEMA,
)
from viseron.domains.object_detector.const import CONFIG_CAMERAS
from viseron.helpers.schemas import FLOAT_MIN_ZERO_MAX_ONE
from viseron.helpers.validators import Maybe

from .const import (
    COMPONENT,
    CONFIG_CUSTOM_MODEL,
    CONFIG_FACE_RECOGNITION,
    CONFIG_HOST,
    CONFIG_IMAGE_SIZE,
    CONFIG_LICENSE_PLATE_RECOGNITION,
    CONFIG_MIN_CONFIDENCE,
    CONFIG_OBJECT_DETECTOR,
    CONFIG_PORT,
    CONFIG_TIMEOUT,
    CONFIG_TRAIN,
    DEFAULT_CUSTOM_MODEL,
    DEFAULT_IMAGE_SIZE,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_TRAIN,
    DESC_COMPONENT,
    DESC_CUSTOM_MODEL,
    DESC_FACE_RECOGNITION,
    DESC_HOST,
    DESC_IMAGE_SIZE,
    DESC_LICENSE_PLATE_RECOGNITION,
    DESC_MIN_CONFIDENCE,
    DESC_OBJECT_DETECTOR,
    DESC_PORT,
    DESC_TIMEOUT,
    DESC_TRAIN,
)

LOGGER = logging.getLogger(__name__)

OBJECT_DETECTOR_SCHEMA = OBJECT_DETECTOR_BASE_CONFIG_SCHEMA.extend(
    {
        vol.Optional(
            CONFIG_IMAGE_SIZE,
            default=DEFAULT_IMAGE_SIZE,
            description=DESC_IMAGE_SIZE,
        ): Maybe(int),
        vol.Optional(
            CONFIG_CUSTOM_MODEL,
            default=DEFAULT_CUSTOM_MODEL,
            description=DESC_CUSTOM_MODEL,
        ): Maybe(str),
    }
)

FACE_RECOGNITION_SCHEMA = FACE_RECOGNITION_BASE_CONFIG_SCHEMA.extend(
    {
        vol.Optional(CONFIG_TRAIN, default=DEFAULT_TRAIN, description=DESC_TRAIN): bool,
        vol.Optional(
            CONFIG_MIN_CONFIDENCE,
            default=DEFAULT_MIN_CONFIDENCE,
            description=DESC_MIN_CONFIDENCE,
        ): FLOAT_MIN_ZERO_MAX_ONE,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): vol.Schema(
            {
                vol.Required(CONFIG_HOST, description=DESC_HOST): str,
                vol.Optional(
                    CONFIG_PORT, default=DEFAULT_PORT, description=DESC_PORT
                ): vol.All(int, vol.Range(min=1024, max=49151)),
                vol.Optional(
                    CONFIG_TIMEOUT, default=DEFAULT_TIMEOUT, description=DESC_TIMEOUT
                ): int,
                vol.Optional(
                    CONFIG_OBJECT_DETECTOR, description=DESC_OBJECT_DETECTOR
                ): OBJECT_DETECTOR_SCHEMA,
                vol.Optional(
                    CONFIG_FACE_RECOGNITION, description=DESC_FACE_RECOGNITION
                ): FACE_RECOGNITION_SCHEMA,
                vol.Optional(
                    CONFIG_LICENSE_PLATE_RECOGNITION,
                    description=DESC_LICENSE_PLATE_RECOGNITION,
                ): LICENSE_PLATE_RECOGNITION_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config) -> bool:
    """Set up the edgetpu component."""
    config = config[COMPONENT]

    if config.get(CONFIG_OBJECT_DETECTOR, None):
        for camera_identifier in config[CONFIG_OBJECT_DETECTOR][CONFIG_CAMERAS].keys():
            setup_domain(
                vis,
                COMPONENT,
                CONFIG_OBJECT_DETECTOR,
                config,
                identifier=camera_identifier,
                require_domains=[
                    RequireDomain(
                        domain="camera",
                        identifier=camera_identifier,
                    )
                ],
                optional_domains=[
                    OptionalDomain(
                        domain=MOTION_DETECTOR_DOMAIN,
                        identifier=camera_identifier,
                    ),
                ],
            )

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
            CodeProjectAITrain(config)

    if config.get(CONFIG_LICENSE_PLATE_RECOGNITION, None):
        for camera_identifier in config[CONFIG_LICENSE_PLATE_RECOGNITION][
            CONFIG_CAMERAS
        ].keys():
            setup_domain(
                vis,
                COMPONENT,
                CONFIG_LICENSE_PLATE_RECOGNITION,
                config,
                identifier=camera_identifier,
                require_domains=[
                    RequireDomain(
                        domain="camera",
                        identifier=camera_identifier,
                    )
                ],
            )

    return True
