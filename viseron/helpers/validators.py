"""Custom voluptuous validators."""
from typing import Callable, Optional

from voluptuous import Invalid


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
