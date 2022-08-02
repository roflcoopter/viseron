"""Custom voluptuous validators."""
import logging
import re
from typing import Any, Callable, Optional

import voluptuous as vol

from viseron.helpers import slugify

LOGGER = logging.getLogger(__name__)
SLUG_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


def deprecated(key: str, replacement: Optional[str] = None) -> Callable[[dict], dict]:
    """Mark key as deprecated and optionally replace it."""

    def validator(config):
        """Warn if key is present. Replace it if a value is given."""
        if key in config:
            if replacement:
                print(
                    f"Config option {key} is deprecated. "
                    f"Replace it with {replacement}. "
                    "In the future this will produce an error"
                )
                value = config[key]
                config.pop(key)

                if replacement not in config:
                    config[replacement] = value
                    return config
                return config
            raise vol.Invalid(
                f"Config option {key} is deprecated. "
                "Please remove it from your configuration"
            )
        return config

    return validator


def ensure_slug(value: str) -> str:
    """Validate a string to only consist of certain characters."""
    regex = re.compile(SLUG_REGEX)
    if not regex.match(value):
        raise vol.Invalid(f"{value} is an invalid slug.")
    return value


def none_to_dict(value):
    """Convert None values to empty dict."""
    if value is None:
        return {}
    return value


def slug(value: Any) -> str:
    """Validate value is a valid slug."""
    if value is None:
        raise vol.Invalid("Slug should not be None")
    str_value = str(value)
    slg = slugify(str_value)
    if str_value == slg:
        return str_value
    msg = f"invalid slug {value} (try {slg})"
    LOGGER.error(msg)
    raise vol.Invalid(msg)


def valid_camera_identifier(value):
    """Check if supplied camera identifier is valid."""
    if not isinstance(value, str):
        msg = f"Camera identifier should be a string. Got {value}"
        LOGGER.error(msg)
        raise vol.Invalid(msg)
    if slug(value):
        return value


class CameraIdentifier(vol.Required):
    """Validate Camera Identifier."""

    def __init__(self, description="Camera identifier."):
        super().__init__(
            valid_camera_identifier,
            description=description,
        )
