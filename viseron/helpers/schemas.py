"""Schema helpers."""

import voluptuous as vol

CONFIG_X = "x"
CONFIG_Y = "y"

DESC_X = "X-coordinate (horizontal axis)."
DESC_Y = "Y-coordinate (vertical axis)."

COORDINATES_SCHEMA = vol.Schema(
    vol.All(
        [
            {
                vol.Required(CONFIG_X, description=DESC_X): int,
                vol.Required(CONFIG_Y, description=DESC_Y): int,
            }
        ],
        vol.Length(min=3),
    )
)

FLOAT_MIN_ZERO_MAX_ONE = vol.Schema(
    vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0))
)

FLOAT_MIN_ZERO = vol.Schema(vol.All(vol.Coerce(float), vol.Range(min=0.0)))

# Strictly positive float, 0 is not a valid value (e.g. fps would divide by zero)
FLOAT_POSITIVE = vol.Schema(
    vol.All(vol.Coerce(float), vol.Range(min=0, min_included=False))
)
