"""Schema helpers."""

import voluptuous as vol

CONFIG_X = "x"
CONFIG_Y = "y"

DESC_X = "X-coordinate (horizontal axis)."
DESC_Y = "Y-coordinate (vertical axis)."

COORDINATES_SCHEMA = vol.Schema(
    [
        {
            vol.Required(CONFIG_X, description=DESC_X): int,
            vol.Required(CONFIG_Y, description=DESC_Y): int,
        }
    ]
)

FLOAT_MIN_ZERO_MAX_ONE = vol.Schema(
    vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0))
)

FLOAT_MIN_ZERO = vol.Schema(vol.All(vol.Coerce(float), vol.Range(min=0.0)))
