"""Custom voluptuous validators."""
import re
from typing import Callable, Optional

from voluptuous import Invalid

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
            raise Invalid(
                f"Config option {key} is deprecated. "
                "Please remove it from your configuration"
            )
        return config

    return validator


def ensure_slug(value: str) -> str:
    """Validate a string to only consist of certain characters."""
    regex = re.compile(SLUG_REGEX)
    if not regex.match(value):
        raise Invalid("Invalid string")
    return value


def none_to_dict(value):
    """Convert None values to empty dict."""
    if value is None:
        return {}
    return value
