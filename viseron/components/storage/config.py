"""Storage component configuration."""
import voluptuous as vol

from viseron.components.storage.const import (
    CONFIG_CREATE_EVENT_CLIP,
    CONFIG_DAYS,
    CONFIG_FACE_RECOGNITION,
    CONFIG_GB,
    CONFIG_HOURS,
    CONFIG_MAX_AGE,
    CONFIG_MAX_SIZE,
    CONFIG_MB,
    CONFIG_MIN_AGE,
    CONFIG_MIN_SIZE,
    CONFIG_MINUTES,
    CONFIG_MOVE_ON_SHUTDOWN,
    CONFIG_OBJECT_DETECTION,
    CONFIG_PATH,
    CONFIG_POLL,
    CONFIG_RECORDINGS,
    CONFIG_SNAPSHOTS,
    CONFIG_TIERS,
    CONFIG_TYPE,
    CONFIG_TYPE_CONTINUOUS,
    CONFIG_TYPE_EVENTS,
    DEFAULT_CREATE_EVENT_CLIP,
    DEFAULT_DAYS,
    DEFAULT_FACE_RECOGNITION,
    DEFAULT_GB,
    DEFAULT_HOURS,
    DEFAULT_MAX_AGE,
    DEFAULT_MAX_SIZE,
    DEFAULT_MB,
    DEFAULT_MIN_AGE,
    DEFAULT_MIN_SIZE,
    DEFAULT_MINUTES,
    DEFAULT_MOVE_ON_SHUTDOWN,
    DEFAULT_OBJECT_DETECTION,
    DEFAULT_POLL,
    DEFAULT_RECORDINGS,
    DEFAULT_RECORDINGS_TIERS,
    DEFAULT_SNAPSHOTS,
    DEFAULT_SNAPSHOTS_TIERS,
    DEFAULT_TYPE,
    DESC_CREATE_EVENT_CLIP,
    DESC_DAYS,
    DESC_DOMAIN_TIERS,
    DESC_FACE_RECOGNITION,
    DESC_GB,
    DESC_HOURS,
    DESC_MAX_AGE,
    DESC_MAX_SIZE,
    DESC_MB,
    DESC_MIN_AGE,
    DESC_MIN_SIZE,
    DESC_MINUTES,
    DESC_MOVE_ON_SHUTDOWN,
    DESC_OBJECT_DETECTION,
    DESC_PATH,
    DESC_POLL,
    DESC_RECORDINGS,
    DESC_RECORDINGS_TIERS,
    DESC_SNAPSHOTS,
    DESC_SNAPSHOTS_TIERS,
    DESC_TYPE,
)
from viseron.helpers.validators import Maybe

SIZE_SCHEMA = {
    vol.Optional(
        CONFIG_GB,
        default=DEFAULT_GB,
        description=DESC_GB,
    ): Maybe(vol.Coerce(float)),
    vol.Optional(
        CONFIG_MB,
        default=DEFAULT_MB,
        description=DESC_MB,
    ): Maybe(vol.Coerce(float)),
}

AGE_SCHEMA = {
    vol.Optional(
        CONFIG_DAYS,
        default=DEFAULT_DAYS,
        description=DESC_DAYS,
    ): Maybe(vol.Coerce(int)),
    vol.Optional(
        CONFIG_HOURS,
        default=DEFAULT_HOURS,
        description=DESC_HOURS,
    ): Maybe(vol.Coerce(int)),
    vol.Optional(
        CONFIG_MINUTES,
        default=DEFAULT_MINUTES,
        description=DESC_MINUTES,
    ): Maybe(vol.Coerce(int)),
}


TIERS_SCHEMA_BASE = vol.Schema(
    {
        vol.Required(CONFIG_PATH, description=DESC_PATH): vol.All(
            str,
        ),
        vol.Optional(
            CONFIG_POLL,
            default=DEFAULT_POLL,
            description=DESC_POLL,
        ): bool,
        vol.Optional(
            CONFIG_MOVE_ON_SHUTDOWN,
            default=DEFAULT_MOVE_ON_SHUTDOWN,
            description=DESC_MOVE_ON_SHUTDOWN,
        ): bool,
        vol.Optional(
            CONFIG_MIN_SIZE,
            default=DEFAULT_MIN_SIZE,
            description=DESC_MIN_SIZE,
        ): SIZE_SCHEMA,
        vol.Optional(
            CONFIG_MAX_SIZE,
            default=DEFAULT_MAX_SIZE,
            description=DESC_MAX_SIZE,
        ): SIZE_SCHEMA,
        vol.Optional(
            CONFIG_MAX_AGE,
            default=DEFAULT_MAX_AGE,
            description=DESC_MAX_AGE,
        ): AGE_SCHEMA,
        vol.Optional(
            CONFIG_MIN_AGE,
            default=DEFAULT_MIN_AGE,
            description=DESC_MIN_AGE,
        ): AGE_SCHEMA,
    }
)

TIERS_SCHEMA = vol.Schema(
    vol.All(
        [TIERS_SCHEMA_BASE],
        vol.Length(min=1),
    )
)

STORAGE_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONFIG_RECORDINGS,
            default=DEFAULT_RECORDINGS,
            description=DESC_RECORDINGS,
        ): {
            vol.Optional(
                CONFIG_CREATE_EVENT_CLIP,
                default=DEFAULT_CREATE_EVENT_CLIP,
                description=DESC_CREATE_EVENT_CLIP,
            ): bool,
            vol.Optional(
                CONFIG_TYPE,
                default=DEFAULT_TYPE,
                description=DESC_TYPE,
            ): vol.In([CONFIG_TYPE_CONTINUOUS, CONFIG_TYPE_EVENTS]),
            vol.Optional(
                CONFIG_TIERS,
                default=DEFAULT_RECORDINGS_TIERS,
                description=DESC_RECORDINGS_TIERS,
            ): TIERS_SCHEMA,
        },
        vol.Optional(
            CONFIG_SNAPSHOTS,
            default=DEFAULT_SNAPSHOTS,
            description=DESC_SNAPSHOTS,
        ): {
            vol.Optional(
                CONFIG_TIERS,
                default=DEFAULT_SNAPSHOTS_TIERS,
                description=DESC_SNAPSHOTS_TIERS,
            ): TIERS_SCHEMA,
            vol.Optional(
                CONFIG_FACE_RECOGNITION,
                default=DEFAULT_FACE_RECOGNITION,
                description=DESC_FACE_RECOGNITION,
            ): Maybe(
                {
                    vol.Required(
                        CONFIG_TIERS, description=DESC_DOMAIN_TIERS
                    ): TIERS_SCHEMA,
                }
            ),
            vol.Optional(
                CONFIG_OBJECT_DETECTION,
                default=DEFAULT_OBJECT_DETECTION,
                description=DESC_OBJECT_DETECTION,
            ): Maybe(
                {
                    vol.Required(
                        CONFIG_TIERS, description=DESC_DOMAIN_TIERS
                    ): TIERS_SCHEMA,
                }
            ),
        },
    }
)
