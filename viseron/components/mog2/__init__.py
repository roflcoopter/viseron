"""MOG2 motion detection."""
import voluptuous as vol

from viseron import Viseron
from viseron.domains import RequireDomain, setup_domain
from viseron.domains.motion_detector import CAMERA_SCHEMA_SCANNER, CONFIG_CAMERAS
from viseron.domains.motion_detector.const import DESC_CAMERAS
from viseron.helpers.validators import CameraIdentifier, CoerceNoneToDict

from .const import (
    COMPONENT,
    CONFIG_DETECT_SHADOWS,
    CONFIG_HISTORY,
    CONFIG_LEARNING_RATE,
    CONFIG_MOTION_DETECTOR,
    CONFIG_THRESHOLD,
    DEFAULT_DETECT_SHADOWS,
    DEFAULT_HISTORY,
    DEFAULT_LEARNING_RATE,
    DEFAULT_THRESHOLD,
    DESC_COMPONENT,
    DESC_DETECT_SHADOWS,
    DESC_HISTORY,
    DESC_LEARNING_RATE,
    DESC_MOTION_DETECTOR,
    DESC_THRESHOLD,
)

CAMERA_SCHEMA = CAMERA_SCHEMA_SCANNER.extend(
    {
        vol.Optional(
            CONFIG_THRESHOLD, default=DEFAULT_THRESHOLD, description=DESC_THRESHOLD
        ): vol.All(int, vol.Range(min=0, max=255)),
        vol.Optional(
            CONFIG_HISTORY, default=DEFAULT_HISTORY, description=DESC_HISTORY
        ): int,
        vol.Optional(
            CONFIG_DETECT_SHADOWS,
            default=DEFAULT_DETECT_SHADOWS,
            description=DESC_DETECT_SHADOWS,
        ): bool,
        vol.Optional(
            CONFIG_LEARNING_RATE,
            default=DEFAULT_LEARNING_RATE,
            description=DESC_LEARNING_RATE,
        ): vol.All(vol.Coerce(float), vol.Range(min=-1, max=1.0)),
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
                        CameraIdentifier(): vol.All(CoerceNoneToDict(), CAMERA_SCHEMA),
                    },
                },
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config):
    """Set up the mog2 component."""
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
