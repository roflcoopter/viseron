"""Schema helpers."""

import voluptuous as vol

CONFIG_X = "x"
CONFIG_Y = "y"

COORDINATES_SCHEMA = vol.Schema(
    [
        {
            vol.Required(CONFIG_X): int,
            vol.Required(CONFIG_Y): int,
        }
    ]
)

MIN_MAX_SCHEMA = vol.Schema(
    vol.All(
        vol.Any(0, 1, vol.All(float, vol.Range(min=0.0, max=1.0))), vol.Coerce(float)
    )
)
