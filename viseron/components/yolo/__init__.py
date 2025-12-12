"""YOLO component."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from viseron import Viseron
from viseron.domains import RequireDomain, setup_domain
from viseron.domains.object_detector import (
    BASE_CONFIG_SCHEMA as OBJECT_DETECTOR_BASE_CONFIG_SCHEMA,
)
from viseron.domains.object_detector.const import CONFIG_CAMERAS
from viseron.helpers.schemas import FLOAT_MIN_ZERO_MAX_ONE
from viseron.helpers.validators import Maybe

from .const import (
    COMPONENT,
    CONFIG_DEVICE,
    CONFIG_HALF_PRECISION,
    CONFIG_IOU,
    CONFIG_MIN_CONFIDENCE,
    CONFIG_MODEL_PATH,
    CONFIG_OBJECT_DETECTOR,
    DEFAULT_DEVICE,
    DEFAULT_HALF_PRECISION,
    DEFAULT_IOU,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MODEL_PATH,
    DESC_COMPONENT,
    DESC_DEVICE,
    DESC_HALF_PRECISION,
    DESC_IOU,
    DESC_MIN_CONFIDENCE,
    DESC_MODEL_PATH,
    DESC_OBJECT_DETECTOR,
)

OBJECT_DETECTOR_SCHEMA = OBJECT_DETECTOR_BASE_CONFIG_SCHEMA.extend(
    {
        vol.Required(
            CONFIG_MODEL_PATH,
            default=DEFAULT_MODEL_PATH,
            description=DESC_MODEL_PATH,
        ): str,
        vol.Optional(
            CONFIG_MIN_CONFIDENCE,
            default=DEFAULT_MIN_CONFIDENCE,
            description=DESC_MIN_CONFIDENCE,
        ): FLOAT_MIN_ZERO_MAX_ONE,
        vol.Optional(
            CONFIG_IOU,
            default=DEFAULT_IOU,
            description=DESC_IOU,
        ): FLOAT_MIN_ZERO_MAX_ONE,
        vol.Optional(
            CONFIG_HALF_PRECISION,
            default=DEFAULT_HALF_PRECISION,
            description=DESC_HALF_PRECISION,
        ): bool,
        vol.Optional(
            CONFIG_DEVICE,
            default=DEFAULT_DEVICE,
            description=DESC_DEVICE,
        ): Maybe(str),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): vol.Schema(
            {
                vol.Required(
                    CONFIG_OBJECT_DETECTOR, description=DESC_OBJECT_DETECTOR
                ): OBJECT_DETECTOR_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config: dict[str, Any]) -> bool:
    """Set up YOLO component."""
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
            )

    return True
