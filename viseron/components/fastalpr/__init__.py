"""fast-alpr component.

Runs license plate detection and OCR locally using the fast-alpr Python package.
No external server (e.g. CodeProject.AI, Deepstack) is required, all inference is
done in-process using ONNX Runtime.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import voluptuous as vol

from viseron import Viseron
from viseron.domains import RequireDomain, setup_domain
from viseron.domains.license_plate_recognition import (
    BASE_CONFIG_SCHEMA as LICENSE_PLATE_RECOGNITION_BASE_CONFIG_SCHEMA,
)
from viseron.domains.post_processor.const import CONFIG_CAMERAS
from viseron.helpers.schemas import FLOAT_MIN_ZERO_MAX_ONE

from .const import (
    COMPONENT,
    CONFIG_DETECTOR_CONF_THRESH,
    CONFIG_DETECTOR_MODEL,
    CONFIG_DEVICE,
    CONFIG_DISCARD_UNRECOGNIZED_PLATES,
    CONFIG_LICENSE_PLATE_RECOGNITION,
    CONFIG_OCR_MODEL,
    DEFAULT_DETECTOR_CONF_THRESH,
    DEFAULT_DETECTOR_MODEL,
    DEFAULT_DEVICE,
    DEFAULT_DISCARD_UNRECOGNIZED_PLATES,
    DEFAULT_OCR_MODEL,
    DESC_COMPONENT,
    DESC_DETECTOR_CONF_THRESH,
    DESC_DETECTOR_MODEL,
    DESC_DEVICE,
    DESC_DISCARD_UNRECOGNIZED_PLATES,
    DESC_LICENSE_PLATE_RECOGNITION,
    DESC_OCR_MODEL,
    INSTANCES,
    LOCK,
    SUPPORTED_DETECTOR_MODELS,
    SUPPORTED_DEVICES,
    SUPPORTED_OCR_MODELS,
)

LOGGER = logging.getLogger(__name__)

LICENSE_PLATE_RECOGNITION_SCHEMA = LICENSE_PLATE_RECOGNITION_BASE_CONFIG_SCHEMA.extend(
    {
        vol.Optional(
            CONFIG_DETECTOR_MODEL,
            default=DEFAULT_DETECTOR_MODEL,
            description=DESC_DETECTOR_MODEL,
        ): vol.In(SUPPORTED_DETECTOR_MODELS),
        vol.Optional(
            CONFIG_DETECTOR_CONF_THRESH,
            default=DEFAULT_DETECTOR_CONF_THRESH,
            description=DESC_DETECTOR_CONF_THRESH,
        ): FLOAT_MIN_ZERO_MAX_ONE,
        vol.Optional(
            CONFIG_OCR_MODEL,
            default=DEFAULT_OCR_MODEL,
            description=DESC_OCR_MODEL,
        ): vol.In(SUPPORTED_OCR_MODELS),
        vol.Optional(
            CONFIG_DEVICE,
            default=DEFAULT_DEVICE,
            description=DESC_DEVICE,
        ): vol.In(SUPPORTED_DEVICES),
        vol.Optional(
            CONFIG_DISCARD_UNRECOGNIZED_PLATES,
            default=DEFAULT_DISCARD_UNRECOGNIZED_PLATES,
            description=DESC_DISCARD_UNRECOGNIZED_PLATES,
        ): bool,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): vol.Schema(
            {
                vol.Optional(
                    CONFIG_LICENSE_PLATE_RECOGNITION,
                    description=DESC_LICENSE_PLATE_RECOGNITION,
                ): LICENSE_PLATE_RECOGNITION_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, _config: dict[str, Any]) -> bool:
    """Set up the fastalpr component."""
    vis.data[COMPONENT] = {LOCK: threading.Lock(), INSTANCES: {}}
    return True


def setup_domains(vis: Viseron, config: dict[str, Any]) -> None:
    """Set up fastalpr domains."""
    config = config[COMPONENT]

    if config.get(CONFIG_LICENSE_PLATE_RECOGNITION, None):
        for camera_identifier in config[CONFIG_LICENSE_PLATE_RECOGNITION][
            CONFIG_CAMERAS
        ]:
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
                    ),
                    RequireDomain(
                        domain="object_detector",
                        identifier=camera_identifier,
                    ),
                ],
            )


def unload(vis: Viseron) -> None:
    """Unload fastalpr component."""
    if COMPONENT in vis.data:
        del vis.data[COMPONENT]
