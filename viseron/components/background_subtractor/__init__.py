"""Background subtraction motion detection."""
import voluptuous as vol

from viseron import Viseron
from viseron.domains import setup_domain
from viseron.domains.motion_detector import (
    BASE_CONFIG_SCHEMA_SCANNER,
    CAMERA_SCHEMA_SCANNER,
    CONFIG_CAMERAS,
)
from viseron.helpers.validators import none_to_dict

from .const import (
    COMPONENT,
    CONFIG_ALPHA,
    CONFIG_MOTION_DETECTOR,
    CONFIG_THRESHOLD,
    DEFAULT_ALPHA,
    DEFAULT_THRESHOLD,
)

CAMERA_SCHEMA = CAMERA_SCHEMA_SCANNER.extend(
    {
        vol.Optional(CONFIG_THRESHOLD, default=DEFAULT_THRESHOLD): vol.All(
            int, vol.Range(min=0, max=255)
        ),
        vol.Optional(CONFIG_ALPHA, default=DEFAULT_ALPHA): vol.All(
            vol.Any(vol.All(float, vol.Range(min=0.0, max=1.0)), 1, 0),
            vol.Coerce(float),
        ),
    }
)


MOTION_DETECTOR_SCHEMA = BASE_CONFIG_SCHEMA_SCANNER.extend(
    {
        vol.Required(CONFIG_CAMERAS): {str: vol.All(none_to_dict, CAMERA_SCHEMA)},
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT: vol.Schema(
            {
                vol.Required(CONFIG_MOTION_DETECTOR): MOTION_DETECTOR_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config):
    """Set up the background_subtractor component."""
    config = config[COMPONENT]
    for domain in config.keys():
        setup_domain(vis, COMPONENT, domain, config)

    return True
