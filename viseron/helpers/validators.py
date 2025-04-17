"""Custom voluptuous validators."""
import logging
from collections.abc import Callable
from typing import Any

import voluptuous as vol

from viseron.helpers import slugify

LOGGER = logging.getLogger(__name__)


class UNDEFINED:
    """Class to represent undefined value.

    This is used in voluptuous schemas to indicate that an optional key
    is not present in the configuration. It is used to differentiate
    between defined and undefined values.
    """

    def __repr__(self) -> str:
        """Return representation."""
        return "UNDEFINED(%s)" % "undefined"

    def __bool__(self):
        """Return False for UNDEFINED."""
        return False

    def __eq__(self, other):
        """Check if other is UNDEFINED."""
        return other is UNDEFINED

    def __ne__(self, other):
        """Check if other is not UNDEFINED."""
        return other is not UNDEFINED


def deprecated(key: str, replacement: str | None = None) -> Callable[[dict], dict]:
    """Mark key as deprecated and optionally replace it.

    Usage example:
    CONFIG_SCHEMA = vol.Schema(
        vol.All(
            {
                vol.Optional(
                    "this_key_is_deprecated"
                ): str,
            },
            deprecated("this_key_is_deprecated", "this_key_is_replacement")
        )
    )
    """

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


class Deprecated(vol.Optional):
    """Mark key as deprecated.

    message: Displayed in the generated documentation.
    warning: Displayed in the logs.
    """

    def __init__(
        self,
        schema: Any,
        raise_error=False,
        message=None,
        description=None,
        warning=None,
    ) -> None:
        self._key = schema
        self._raise_error = raise_error
        self._message = message
        self._warning = warning

        super().__init__(
            schema,
            default=vol.UNDEFINED,
            description=description,
        )

    @property
    def key(self) -> str:
        """Return deprecated key."""
        return self._key

    @property
    def message(self) -> str:
        """Return deprecation message."""
        return (
            f"Config option '{self.key}' is deprecated "
            "and will be removed in a future version."
            if not self._message
            else self._message
        )

    @property
    def warning(self) -> str:
        """Return deprecation warning."""
        return (
            f"Config option '{self.key}' is deprecated "
            "and will be removed in a future version. "
            "Please remove it from your configuration."
            if not self._warning
            else self._warning
        )

    def __call__(self, v):
        """Warn user about deprecated key."""
        if self._raise_error:
            raise vol.Invalid(self.warning)
        LOGGER.warning(self.warning)
        return super().__call__(v)


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


def valid_camera_identifier(value: Any) -> str:
    """Check if supplied camera identifier is valid."""
    if not isinstance(value, str):
        msg = f"Camera identifier should be a string. Got {value}"
        LOGGER.error(msg)
        raise vol.Invalid(msg)
    return slug(value)


def request_argument_no_value(value) -> bool:
    """Return true for given request arguments without value."""
    if value or (isinstance(value, str) and value == ""):
        return True
    return False


class CameraIdentifier(vol.Required):
    """Validate Camera Identifier."""

    def __init__(
        self,
        description: str = (
            "Camera identifier. "
            "Valid characters are lowercase a-z, numbers and underscores."
        ),
    ) -> None:
        super().__init__(
            valid_camera_identifier,
            description=description,
        )


class CoerceNoneToDict:
    """Coerce None to empty dict."""

    def __init__(self) -> None:
        pass

    def __call__(self, value: dict[str, None] | None) -> dict[str, None]:
        """Coerce None to empty dict."""
        if isinstance(value, dict):
            return value

        if value is None:
            return {}
        raise vol.CoerceInvalid("expected dict or None")

    def __repr__(self) -> str:
        """Return representation."""
        return "CoerceNoneToDict(%s)" % "dict"


class Maybe(vol.Any):
    """Mimic voluptuous.Maybe but using a class instead.

    This allows for special handling when generating docs with scripts/gen_docs.py.
    """

    def __init__(self, *validators, **kwargs) -> None:
        super().__init__(
            *validators
            + (
                None,
                UNDEFINED,
            ),
            **kwargs,
        )


class Slug:
    """Ensure value is in proper slug-format."""

    def __init__(
        self,
        description: str = (
            "Slug, valid characters are lowercase a-z, numbers and underscores."
        ),
    ) -> None:
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
