"""Background subtraction motion detection."""
import voluptuous as vol

from viseron import Viseron
from viseron.domains import RequireDomain, setup_domain
from viseron.domains.motion_detector import CAMERA_SCHEMA_SCANNER, CONFIG_CAMERAS
from viseron.domains.motion_detector.const import DESC_CAMERAS
from viseron.helpers.schemas import FLOAT_MIN_ZERO_MAX_ONE
from viseron.helpers.validators import CameraIdentifier, CoerceNoneToDict

from .const import (
    COMPONENT,
    CONFIG_ALPHA,
    CONFIG_MOTION_DETECTOR,
    CONFIG_THRESHOLD,
    DEFAULT_ALPHA,
    DEFAULT_THRESHOLD,
    DESC_ALPHA,
    DESC_COMPONENT,
    DESC_MOTION_DETECTOR,
    DESC_THRESHOLD,
)

CAMERA_SCHEMA = CAMERA_SCHEMA_SCANNER.extend(
    {
        vol.Optional(
            CONFIG_THRESHOLD, default=DEFAULT_THRESHOLD, description=DESC_THRESHOLD
        ): vol.All(int, vol.Range(min=0, max=255)),
        vol.Optional(
            CONFIG_ALPHA, default=DEFAULT_ALPHA, description=DESC_ALPHA
        ): FLOAT_MIN_ZERO_MAX_ONE,
    }
)


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(COMPONENT, description=DESC_COMPONENT): vol.Schema(
            {
                vol.Required(
                    CONFIG_MOTION_DETECTOR, description=DESC_MOTION_DETECTOR
                ): {
                    vol.Required(CONFIG_CAMERAS, description=DESC_CAMERAS): {
                        CameraIdentifier(): CoerceNoneToDict(CAMERA_SCHEMA)
                    },
                },
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config):
    """Set up the background_subtractor component."""
    config = config[COMPONENT]
    for camera_identifier in config[CONFIG_MOTION_DETECTOR][CONFIG_CAMERAS].keys():
        setup_domain(
            vis,
            COMPONENT,
            CONFIG_MOTION_DETECTOR,
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
