"""Custom voluptuous validators."""
import logging
from typing import Any, Callable, Optional

import voluptuous as vol

from viseron.helpers import slugify

LOGGER = logging.getLogger(__name__)


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


def request_argument_no_value(value):
    """Return true for given request arguments without value."""
    if value or (isinstance(value, str) and value == ""):
        return True
    return False


class CameraIdentifier(vol.Required):
    """Validate Camera Identifier."""

    def __init__(
        self,
        description=(
            "Camera identifier. "
            "Valid characters are lowercase a-z, numbers and underscores."
        ),
    ):
        super().__init__(
            valid_camera_identifier,
            description=description,
        )


class CoerceNoneToDict:
    """Coerce None to empty dict."""

    def __init__(self):
        pass

    def __call__(self, value):
        """Coerce None to empty dict."""
        if isinstance(value, dict):
            return value

        if value is None:
            return {}
        raise vol.CoerceInvalid("expected dict or None")

    def __repr__(self):
        """Return representation."""
        return "CoerceNoneToDict(%s)" % "dict"


class Maybe(vol.Any):
    """Mimic voluptuous.Maybe but using a class instead.

    This allows for special handling when generating docs with scripts/gen_docs.py.
    """

    def __init__(self, *validators, **kwargs):
        super().__init__(*validators + (None,), **kwargs)


class Slug:
    """Ensure value is in proper slug-format."""

    def __init__(
        self,
        description=(
            "Slug, valid characters are lowercase a-z, numbers and underscores."
        ),
    ):
        self.description = description

    def __call__(self, value):
        """Ensure slug."""
        if not isinstance(value, str):
            msg = f"Expected slug, valid characters are [a-z] and [_]. Got {value}"
            LOGGER.error(msg)
            raise vol.Invalid(msg)
        if slug(value):
            return value
        raise vol.Invalid("Invalid slug.")


def request_argument_bool(value):
    """Boolean HTTP request argument.

    Any boolean value works, but also accepts 'true' and 'false' as strings.
    Examples:
        1 => True
        0 => False
        'true' => True
        'false' => False
        'foo' => True
        '' => False
    """
    if value == "true":
        return True
    if value == "false":
        return False
    return bool(value)
