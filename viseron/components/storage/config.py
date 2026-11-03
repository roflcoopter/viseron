"""Storage component configuration."""

from __future__ import annotations

import os
from datetime import timedelta
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal

import voluptuous as vol
from pydantic import AfterValidator, Field, ValidationError, model_validator
from pydantic_core import PydanticCustomError
from typing_extensions import Self

from viseron.components.storage.const import (
    COMPONENT,
    CONFIG_CHECK_INTERVAL,
    CONFIG_CONTINUOUS,
    CONFIG_DAYS,
    CONFIG_DRAIN,
    CONFIG_EVENTS,
    CONFIG_FACE_RECOGNITION,
    CONFIG_GB,
    CONFIG_HOURS,
    CONFIG_IMAGE_CLASSIFICATION,
    CONFIG_INTERVAL,
    CONFIG_LICENSE_PLATE_RECOGNITION,
    CONFIG_MAX_AGE,
    CONFIG_MAX_SIZE,
    CONFIG_MB,
    CONFIG_MIN_AGE,
    CONFIG_MIN_SIZE,
    CONFIG_MINUTES,
    CONFIG_MOTION_DETECTOR,
    CONFIG_MOVE_ON_SHUTDOWN,
    CONFIG_OBJECT_DETECTOR,
    CONFIG_PATH,
    CONFIG_POLL,
    CONFIG_RECORDER,
    CONFIG_SECONDS,
    CONFIG_SNAPSHOTS,
    CONFIG_TIERS,
    CONFIG_TIMELAPSE,
    DEFAULT_CHECK_INTERVAL,
    DEFAULT_CHECK_INTERVAL_DAYS,
    DEFAULT_CHECK_INTERVAL_HOURS,
    DEFAULT_CHECK_INTERVAL_MINUTES,
    DEFAULT_CHECK_INTERVAL_SECONDS,
    DEFAULT_COMPONENT,
    DEFAULT_CONTINUOUS,
    DEFAULT_DAYS,
    DEFAULT_DRAIN,
    DEFAULT_EVENTS,
    DEFAULT_FACE_RECOGNITION,
    DEFAULT_GB,
    DEFAULT_HOURS,
    DEFAULT_IMAGE_CLASSIFICATION,
    DEFAULT_INTERVAL,
    DEFAULT_LICENSE_PLATE_RECOGNITION,
    DEFAULT_MAX_AGE,
    DEFAULT_MAX_SIZE,
    DEFAULT_MB,
    DEFAULT_MIN_AGE,
    DEFAULT_MIN_SIZE,
    DEFAULT_MINUTES,
    DEFAULT_MOTION_DETECTOR,
    DEFAULT_MOVE_ON_SHUTDOWN,
    DEFAULT_OBJECT_DETECTOR,
    DEFAULT_POLL,
    DEFAULT_RECORDER,
    DEFAULT_RECORDER_TIERS,
    DEFAULT_SECONDS,
    DEFAULT_SNAPSHOTS,
    DEFAULT_SNAPSHOTS_TIERS,
    DEFAULT_TIER_CHECK_BATCH_SIZE,
    DEFAULT_TIER_CHECK_CPU_LIMIT,
    DEFAULT_TIER_CHECK_SLEEP_BETWEEN_BATCHES,
    DEFAULT_TIER_CHECK_WORKERS,
    DEFAULT_TIMELAPSE,
    DESC_CHECK_INTERVAL,
    DESC_CHECK_INTERVAL_DAYS,
    DESC_CHECK_INTERVAL_HOURS,
    DESC_CHECK_INTERVAL_MINUTES,
    DESC_CHECK_INTERVAL_SECONDS,
    DESC_COMPONENT,
    DESC_CONTINUOUS,
    DESC_DOMAIN_TIERS,
    DESC_DRAIN,
    DESC_EVENTS,
    DESC_FACE_RECOGNITION,
    DESC_IMAGE_CLASSIFICATION,
    DESC_INTERVAL,
    DESC_INTERVAL_DAYS,
    DESC_INTERVAL_HOURS,
    DESC_INTERVAL_MINUTES,
    DESC_INTERVAL_SECONDS,
    DESC_LICENSE_PLATE_RECOGNITION,
    DESC_MAX_AGE,
    DESC_MAX_DAYS,
    DESC_MAX_GB,
    DESC_MAX_HOURS,
    DESC_MAX_MB,
    DESC_MAX_MINUTES,
    DESC_MAX_SIZE,
    DESC_MIN_AGE,
    DESC_MIN_DAYS,
    DESC_MIN_GB,
    DESC_MIN_HOURS,
    DESC_MIN_MB,
    DESC_MIN_MINUTES,
    DESC_MIN_SIZE,
    DESC_MOTION_DETECTOR,
    DESC_MOVE_ON_SHUTDOWN,
    DESC_OBJECT_DETECTOR,
    DESC_PATH,
    DESC_POLL,
    DESC_RECORDER,
    DESC_RECORDER_TIERS,
    DESC_SNAPSHOTS,
    DESC_SNAPSHOTS_TIERS,
    DESC_TIER_CHECK_BATCH_SIZE,
    DESC_TIER_CHECK_CPU_LIMIT,
    DESC_TIER_CHECK_SLEEP_BETWEEN_BATCHES,
    DESC_TIER_CHECK_WORKERS,
    DESC_TIMELAPSE,
    DESC_TIMELAPSE_TIERS,
    TIER_CATEGORY_RECORDER,
    TIER_CATEGORY_SNAPSHOTS,
    TIER_CATEGORY_TIMELAPSE,
    TIER_SUBCATEGORY_EVENT_CLIPS,
    TIER_SUBCATEGORY_FACE_RECOGNITION,
    TIER_SUBCATEGORY_IMAGE_CLASSIFICATION,
    TIER_SUBCATEGORY_LICENSE_PLATE_RECOGNITION,
    TIER_SUBCATEGORY_MOTION_DETECTOR,
    TIER_SUBCATEGORY_OBJECT_DETECTOR,
    TIER_SUBCATEGORY_SEGMENTS,
    TIER_SUBCATEGORY_THUMBNAILS,
)
from viseron.config import UNSUPPORTED
from viseron.const import TEMP_DIR
from viseron.helpers.config_model import ComponentRoot, ConfigModel
from viseron.helpers.config_types import NoneToDict
from viseron.helpers.config_validation import format_validation_error
from viseron.helpers.validators import UNDEFINED, CoerceNoneToDict, Maybe

if TYPE_CHECKING:
    from collections.abc import Iterable


def _ends_with_slash(value: str) -> str:
    return value if value.endswith("/") else f"{value}/"


TierPath = Annotated[str, Field(min_length=1), AfterValidator(_ends_with_slash)]


class Size(ConfigModel):
    """A size. Gigabytes and megabytes are added together."""

    gb: float | None = DEFAULT_GB
    mb: float | None = DEFAULT_MB

    def to_bytes(self) -> int:
        """Return the size in bytes."""
        return int((self.gb or 0) * 1024**3 + (self.mb or 0) * 1024**2)


class MinSize(Size):
    """Minimum size of a tier."""

    gb: float | None = Field(default=DEFAULT_GB, description=DESC_MIN_GB)
    mb: float | None = Field(default=DEFAULT_MB, description=DESC_MIN_MB)


class MaxSize(Size):
    """Maximum size of a tier."""

    gb: float | None = Field(default=DEFAULT_GB, description=DESC_MAX_GB)
    mb: float | None = Field(default=DEFAULT_MB, description=DESC_MAX_MB)


class Age(ConfigModel):
    """An age. Days, hours and minutes are added together."""

    days: int | None = DEFAULT_DAYS
    hours: int | None = DEFAULT_HOURS
    minutes: int | None = DEFAULT_MINUTES

    def to_timedelta(self) -> timedelta:
        """Return the age as a timedelta."""
        return timedelta(
            days=self.days or 0, hours=self.hours or 0, minutes=self.minutes or 0
        )


class MinAge(Age):
    """Minimum age of the files in a tier."""

    days: int | None = Field(default=DEFAULT_DAYS, description=DESC_MIN_DAYS)
    hours: int | None = Field(default=DEFAULT_HOURS, description=DESC_MIN_HOURS)
    minutes: int | None = Field(default=DEFAULT_MINUTES, description=DESC_MIN_MINUTES)


class MaxAge(Age):
    """Maximum age of the files in a tier."""

    days: int | None = Field(default=DEFAULT_DAYS, description=DESC_MAX_DAYS)
    hours: int | None = Field(default=DEFAULT_HOURS, description=DESC_MAX_HOURS)
    minutes: int | None = Field(default=DEFAULT_MINUTES, description=DESC_MAX_MINUTES)


class CheckInterval(ConfigModel):
    """How often a tier is checked for files to move or delete."""

    days: int = Field(
        default=DEFAULT_CHECK_INTERVAL_DAYS, ge=0, description=DESC_CHECK_INTERVAL_DAYS
    )
    hours: int = Field(
        default=DEFAULT_CHECK_INTERVAL_HOURS,
        ge=0,
        description=DESC_CHECK_INTERVAL_HOURS,
    )
    minutes: int = Field(
        default=DEFAULT_CHECK_INTERVAL_MINUTES,
        ge=0,
        description=DESC_CHECK_INTERVAL_MINUTES,
    )
    seconds: int = Field(
        default=DEFAULT_CHECK_INTERVAL_SECONDS,
        ge=0,
        description=DESC_CHECK_INTERVAL_SECONDS,
    )

    def to_timedelta(self) -> timedelta:
        """Return the interval as a timedelta."""
        return timedelta(
            days=self.days, hours=self.hours, minutes=self.minutes, seconds=self.seconds
        )


class TimelapseInterval(ConfigModel):
    """Time between the timelapse frames that are kept in a tier."""

    days: int | None = Field(default=DEFAULT_DAYS, description=DESC_INTERVAL_DAYS)
    hours: int | None = Field(default=DEFAULT_HOURS, description=DESC_INTERVAL_HOURS)
    minutes: int | None = Field(
        default=DEFAULT_MINUTES, description=DESC_INTERVAL_MINUTES
    )
    seconds: int | None = Field(
        default=DEFAULT_SECONDS, description=DESC_INTERVAL_SECONDS
    )

    def to_timedelta(self) -> timedelta:
        """Return the interval as a timedelta."""
        return timedelta(
            days=self.days or 0,
            hours=self.hours or 0,
            minutes=self.minutes or 0,
            seconds=self.seconds or 0,
        )


class TierRetention(ConfigModel):
    """Rules for when files are moved to the next tier or deleted."""

    min_size: Annotated[MinSize, NoneToDict] = Field(
        default=DEFAULT_MIN_SIZE, validate_default=True, description=DESC_MIN_SIZE
    )
    max_size: Annotated[MaxSize, NoneToDict] = Field(
        default=DEFAULT_MAX_SIZE, validate_default=True, description=DESC_MAX_SIZE
    )
    max_age: Annotated[MaxAge, NoneToDict] = Field(
        default=DEFAULT_MAX_AGE, validate_default=True, description=DESC_MAX_AGE
    )
    min_age: Annotated[MinAge, NoneToDict] = Field(
        default=DEFAULT_MIN_AGE, validate_default=True, description=DESC_MIN_AGE
    )

    @property
    def enabled(self) -> bool:
        """Return if any rule is set."""
        return any(
            (
                self.max_size.to_bytes(),
                self.min_age.to_timedelta(),
                self.min_size.to_bytes(),
                self.max_age.to_timedelta(),
            )
        )


class Tier(ConfigModel):
    """The common keys for all kinds of storage tiers."""

    path: TierPath = Field(description=DESC_PATH)
    poll: bool = Field(default=DEFAULT_POLL, description=DESC_POLL)
    move_on_shutdown: bool = Field(
        default=DEFAULT_MOVE_ON_SHUTDOWN, description=DESC_MOVE_ON_SHUTDOWN
    )
    drain: bool = Field(default=DEFAULT_DRAIN, description=DESC_DRAIN)
    check_interval: Annotated[CheckInterval, NoneToDict] = Field(
        default=DEFAULT_CHECK_INTERVAL,
        validate_default=True,
        description=DESC_CHECK_INTERVAL,
    )


class RecorderTier(Tier):
    """A recorder tier with separate rules for continuous and event recordings."""

    continuous: Annotated[TierRetention, NoneToDict] = Field(
        default=DEFAULT_CONTINUOUS, validate_default=True, description=DESC_CONTINUOUS
    )
    events: Annotated[TierRetention, NoneToDict] = Field(
        default=DEFAULT_EVENTS, validate_default=True, description=DESC_EVENTS
    )


class SnapshotsTier(Tier, TierRetention):
    """A snapshots tier."""


class TimelapseTier(SnapshotsTier):
    """A timelapse tier."""

    interval: Annotated[TimelapseInterval, NoneToDict] = Field(
        default=DEFAULT_INTERVAL, validate_default=True, description=DESC_INTERVAL
    )


RecorderTiers = Annotated[list[RecorderTier], Field(min_length=1)]
SnapshotsTiers = Annotated[list[SnapshotsTier], Field(min_length=1)]
TimelapseTiers = Annotated[list[TimelapseTier], Field(min_length=1)]


def _tier_error(path: str, message: str) -> PydanticCustomError:
    return PydanticCustomError("storage_tier", message, {"path": path})


def _check_path_exists(path: str, category: str) -> None:
    """Check that the folders of a tier are mounted."""
    if path == "/":
        if category == TIER_CATEGORY_RECORDER:
            folders = [
                f"/{TIER_SUBCATEGORY_SEGMENTS}",
                f"/{TIER_SUBCATEGORY_EVENT_CLIPS}",
                f"/{TIER_SUBCATEGORY_THUMBNAILS}",
            ]
        else:
            folders = [f"/{category}"]
    else:
        folders = [path]

    for folder in folders:
        if not os.path.exists(folder):
            raise _tier_error(
                folder,
                "The {path} folder does not exist. Please mount it to the container.",
            )


def _check_tiers(tiers: Iterable[tuple[str, MaxAge]], category: str) -> None:
    """Check the tiers of one kind of file, in the order they are used.

    Rules:
    - Paths cannot be reserved paths.
    - The same path cannot be used twice.
    - The path has to exist.
    - max_age has to be greater than max_age of the previous tier.
    """
    paths: list[str] = []
    previous_max_age: timedelta | None = None
    for path, max_age in tiers:
        if os.path.normpath(path) in ["/tmp", TEMP_DIR]:
            raise _tier_error(path, "Tier {path} is a reserved path and cannot be used")
        if path in paths:
            raise _tier_error(path, "Tier {path} is defined multiple times")
        paths.append(path)

        _check_path_exists(path, category)

        tier_max_age = max_age.to_timedelta()
        if (
            previous_max_age is not None
            and timedelta(0) < tier_max_age <= previous_max_age
        ):
            raise _tier_error(
                path, "Tier {path} max_age must be greater than previous tier max_age"
            )
        previous_max_age = tier_max_age


class RecorderConfig(ConfigModel):
    """Tiers of the recordings."""

    tiers: RecorderTiers = Field(
        default=DEFAULT_RECORDER_TIERS,
        validate_default=True,
        description=DESC_RECORDER_TIERS,
    )

    @model_validator(mode="after")
    def _validate_tiers(self) -> Self:
        """Check the tiers of continuous and event recordings.

        Continuous and event recordings can only be enabled in a tier if they are
        enabled in the first tier.
        """
        first_tier, *other_tiers = self.tiers
        for tier in other_tiers:
            if not first_tier.continuous.enabled and tier.continuous.enabled:
                raise PydanticCustomError(
                    "storage_tier",
                    "Continuous recordings is not enabled in the first tier and thus "
                    "cannot be enabled in any subsequent tier",
                )
            if not first_tier.events.enabled and tier.events.enabled:
                raise PydanticCustomError(
                    "storage_tier",
                    "Event recordings is not enabled in the first tier and thus "
                    "cannot be enabled in any subsequent tier",
                )

        _check_tiers(
            ((tier.path, tier.events.max_age) for tier in self.tiers),
            TIER_CATEGORY_RECORDER,
        )
        _check_tiers(
            ((tier.path, tier.continuous.max_age) for tier in self.tiers),
            TIER_CATEGORY_RECORDER,
        )
        return self


# The keys of SnapshotsConfig that set the tiers of one domain
SNAPSHOT_DOMAINS: Final = (
    TIER_SUBCATEGORY_FACE_RECOGNITION,
    TIER_SUBCATEGORY_IMAGE_CLASSIFICATION,
    TIER_SUBCATEGORY_OBJECT_DETECTOR,
    TIER_SUBCATEGORY_LICENSE_PLATE_RECOGNITION,
    TIER_SUBCATEGORY_MOTION_DETECTOR,
)


class DomainTiers(ConfigModel):
    """Tiers of the snapshots of one domain."""

    tiers: SnapshotsTiers = Field(description=DESC_DOMAIN_TIERS)


class SnapshotsConfig(ConfigModel):
    """Tiers of the snapshots, with optional tiers per domain."""

    tiers: SnapshotsTiers = Field(
        default=DEFAULT_SNAPSHOTS_TIERS,
        validate_default=True,
        description=DESC_SNAPSHOTS_TIERS,
    )
    face_recognition: DomainTiers | None = Field(
        default=DEFAULT_FACE_RECOGNITION, description=DESC_FACE_RECOGNITION
    )
    image_classification: DomainTiers | None = Field(
        default=DEFAULT_IMAGE_CLASSIFICATION, description=DESC_IMAGE_CLASSIFICATION
    )
    object_detector: DomainTiers | None = Field(
        default=DEFAULT_OBJECT_DETECTOR, description=DESC_OBJECT_DETECTOR
    )
    license_plate_recognition: DomainTiers | None = Field(
        default=DEFAULT_LICENSE_PLATE_RECOGNITION,
        description=DESC_LICENSE_PLATE_RECOGNITION,
    )
    motion_detector: DomainTiers | None = Field(
        default=DEFAULT_MOTION_DETECTOR, description=DESC_MOTION_DETECTOR
    )

    def domain_tiers(self, domain: str) -> list[SnapshotsTier]:
        """Return the tiers of a domain, which are the common tiers if not set."""
        domain_config: DomainTiers | None = getattr(self, domain)
        return domain_config.tiers if domain_config else self.tiers

    def tier_lists(self) -> list[list[SnapshotsTier]]:
        """Return the common tiers and the tiers of each domain that sets them."""
        tier_lists = [self.tiers]
        for domain in SNAPSHOT_DOMAINS:
            domain_config: DomainTiers | None = getattr(self, domain)
            if domain_config:
                tier_lists.append(domain_config.tiers)
        return tier_lists

    @model_validator(mode="after")
    def _validate_tiers(self) -> Self:
        """Check the common tiers and the tiers of each domain on their own."""
        for tiers in self.tier_lists():
            _check_tiers(
                ((tier.path, tier.max_age) for tier in tiers), TIER_CATEGORY_SNAPSHOTS
            )
        return self


class TimelapseConfig(ConfigModel):
    """Tiers of the timelapse frames."""

    tiers: TimelapseTiers = Field(description=DESC_TIMELAPSE_TIERS)

    @model_validator(mode="after")
    def _validate_tiers(self) -> Self:
        _check_tiers(
            ((tier.path, tier.max_age) for tier in self.tiers), TIER_CATEGORY_TIMELAPSE
        )
        return self


class StorageConfig(ConfigModel):
    """Storage configuration."""

    tier_check_cpu_limit: int = Field(
        default=DEFAULT_TIER_CHECK_CPU_LIMIT, description=DESC_TIER_CHECK_CPU_LIMIT
    )
    tier_check_workers: int = Field(
        default=DEFAULT_TIER_CHECK_WORKERS, ge=1, description=DESC_TIER_CHECK_WORKERS
    )
    tier_check_batch_size: int = Field(
        default=DEFAULT_TIER_CHECK_BATCH_SIZE, description=DESC_TIER_CHECK_BATCH_SIZE
    )
    tier_check_sleep_between_batches: float = Field(
        default=DEFAULT_TIER_CHECK_SLEEP_BETWEEN_BATCHES,
        description=DESC_TIER_CHECK_SLEEP_BETWEEN_BATCHES,
    )
    recorder: Annotated[RecorderConfig, NoneToDict] = Field(
        default=DEFAULT_RECORDER, validate_default=True, description=DESC_RECORDER
    )
    snapshots: Annotated[SnapshotsConfig, NoneToDict] = Field(
        default=DEFAULT_SNAPSHOTS, validate_default=True, description=DESC_SNAPSHOTS
    )
    timelapse: TimelapseConfig | None = Field(
        default=DEFAULT_TIMELAPSE, description=DESC_TIMELAPSE
    )


class StorageRoot(ComponentRoot):
    """Root model of the storage component."""

    storage: Annotated[StorageConfig, NoneToDict] = Field(
        default=DEFAULT_COMPONENT, validate_default=True, description=DESC_COMPONENT
    )


def validate_tiers(config: dict[str, Any]) -> dict[str, Any]:
    """Check the tiers that a camera sets in its storage config.

    The camera config is still validated by Voluptuous so this can be removed once
    the camera domain has been migrated.
    """
    camera_storage: dict[str, Any] = config[COMPONENT]
    sections: dict[str, type[ConfigModel]] = {
        CONFIG_RECORDER: RecorderConfig,
        CONFIG_SNAPSHOTS: SnapshotsConfig,
        CONFIG_TIMELAPSE: TimelapseConfig,
    }
    for key, model in sections.items():
        # Keys that the camera does not set are UNDEFINED, which is falsy
        if section := camera_storage.get(key):
            try:
                model.model_validate(
                    {
                        section_key: value
                        for section_key, value in section.items()
                        if not isinstance(value, UNDEFINED)
                    }
                )
            except ValidationError as error:
                raise vol.Invalid(format_validation_error(error)) from error
    return config


# Voluptuous schemas of the tiers that a camera can set in its own config. They are
# used by viseron/domains/camera/config.py, and are removed when it is ported.


def custom_convert(value) -> dict[str, str] | object:
    """Convert custom validators for the script gen_docs."""
    if isinstance(value, CoerceEndsWithSlash):
        return {
            "type": "string",
        }
    return UNSUPPORTED


class CoerceEndsWithSlash:
    """Validate that a path ends with slash."""

    def __init__(self) -> None:
        pass

    def __call__(self, value: str) -> str:
        """Validate that a path ends with slash."""
        if value == "/":
            return value
        if value[-1] != "/":
            return value + "/"
        return value


def get_size_schema(
    age_type: Literal["min"] | Literal["max"],
) -> dict[vol.Optional, Maybe]:
    """Get size schema."""
    return {
        vol.Optional(
            CONFIG_GB,
            default=DEFAULT_GB,
            description=DESC_MIN_GB if age_type == "min" else DESC_MAX_GB,
        ): Maybe(vol.Coerce(float)),
        vol.Optional(
            CONFIG_MB,
            default=DEFAULT_MB,
            description=DESC_MIN_MB if age_type == "min" else DESC_MAX_MB,
        ): Maybe(vol.Coerce(float)),
    }


def get_age_schema(
    age_type: Literal["min"] | Literal["max"],
) -> dict[vol.Optional, Maybe]:
    """Get age schema."""
    return {
        vol.Optional(
            CONFIG_DAYS,
            default=DEFAULT_DAYS,
            description=DESC_MIN_DAYS if age_type == "min" else DESC_MAX_DAYS,
        ): Maybe(vol.Coerce(int)),
        vol.Optional(
            CONFIG_HOURS,
            default=DEFAULT_HOURS,
            description=DESC_MIN_HOURS if age_type == "min" else DESC_MAX_HOURS,
        ): Maybe(vol.Coerce(int)),
        vol.Optional(
            CONFIG_MINUTES,
            default=DEFAULT_MINUTES,
            description=DESC_MIN_MINUTES if age_type == "min" else DESC_MAX_MINUTES,
        ): Maybe(vol.Coerce(int)),
    }


TIER_SCHEMA_BASE = vol.Schema(
    {
        vol.Optional(
            CONFIG_MIN_SIZE,
            default=DEFAULT_MIN_SIZE,
            description=DESC_MIN_SIZE,
        ): get_size_schema("min"),
        vol.Optional(
            CONFIG_MAX_SIZE,
            default=DEFAULT_MAX_SIZE,
            description=DESC_MAX_SIZE,
        ): get_size_schema("max"),
        vol.Optional(
            CONFIG_MAX_AGE,
            default=DEFAULT_MAX_AGE,
            description=DESC_MAX_AGE,
        ): get_age_schema("max"),
        vol.Optional(
            CONFIG_MIN_AGE,
            default=DEFAULT_MIN_AGE,
            description=DESC_MIN_AGE,
        ): get_age_schema("min"),
    }
)

TIER_SCHEMA_SNAPSHOTS = TIER_SCHEMA_BASE.extend(
    {
        vol.Required(
            CONFIG_PATH,
            description=DESC_PATH,
        ): vol.All(str, CoerceEndsWithSlash()),
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
            CONFIG_DRAIN,
            default=DEFAULT_DRAIN,
            description=DESC_DRAIN,
        ): bool,
        vol.Optional(
            CONFIG_CHECK_INTERVAL,
            default=DEFAULT_CHECK_INTERVAL,
            description=DESC_CHECK_INTERVAL,
        ): vol.All(
            CoerceNoneToDict(),
            {
                vol.Optional(
                    CONFIG_DAYS,
                    default=DEFAULT_CHECK_INTERVAL_DAYS,
                    description=DESC_CHECK_INTERVAL_DAYS,
                ): vol.All(int, vol.Range(min=0)),
                vol.Optional(
                    CONFIG_HOURS,
                    default=DEFAULT_CHECK_INTERVAL_HOURS,
                    description=DESC_CHECK_INTERVAL_HOURS,
                ): vol.All(int, vol.Range(min=0)),
                vol.Optional(
                    CONFIG_MINUTES,
                    default=DEFAULT_CHECK_INTERVAL_MINUTES,
                    description=DESC_CHECK_INTERVAL_MINUTES,
                ): vol.All(int, vol.Range(min=0)),
                vol.Optional(
                    CONFIG_SECONDS,
                    default=DEFAULT_CHECK_INTERVAL_SECONDS,
                    description=DESC_CHECK_INTERVAL_SECONDS,
                ): vol.All(int, vol.Range(min=0)),
            },
        ),
    }
)

TIER_SCHEMA_RECORDER = vol.Schema(
    {
        vol.Required(
            CONFIG_PATH,
            description=DESC_PATH,
        ): vol.All(str, CoerceEndsWithSlash()),
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
            CONFIG_DRAIN,
            default=DEFAULT_DRAIN,
            description=DESC_DRAIN,
        ): bool,
        vol.Optional(
            CONFIG_CHECK_INTERVAL,
            default=DEFAULT_CHECK_INTERVAL,
            description=DESC_CHECK_INTERVAL,
        ): vol.All(
            CoerceNoneToDict(),
            {
                vol.Optional(
                    CONFIG_DAYS,
                    default=DEFAULT_CHECK_INTERVAL_DAYS,
                    description=DESC_CHECK_INTERVAL_DAYS,
                ): vol.All(int, vol.Range(min=0)),
                vol.Optional(
                    CONFIG_HOURS,
                    default=DEFAULT_CHECK_INTERVAL_HOURS,
                    description=DESC_CHECK_INTERVAL_HOURS,
                ): vol.All(int, vol.Range(min=0)),
                vol.Optional(
                    CONFIG_MINUTES,
                    default=DEFAULT_CHECK_INTERVAL_MINUTES,
                    description=DESC_CHECK_INTERVAL_MINUTES,
                ): vol.All(int, vol.Range(min=0)),
                vol.Optional(
                    CONFIG_SECONDS,
                    default=DEFAULT_CHECK_INTERVAL_SECONDS,
                    description=DESC_CHECK_INTERVAL_SECONDS,
                ): vol.All(int, vol.Range(min=0)),
            },
        ),
        vol.Optional(
            CONFIG_CONTINUOUS,
            default=DEFAULT_CONTINUOUS,
            description=DESC_CONTINUOUS,
        ): vol.All(CoerceNoneToDict(), TIER_SCHEMA_BASE),
        vol.Optional(
            CONFIG_EVENTS,
            default=DEFAULT_EVENTS,
            description=DESC_EVENTS,
        ): vol.All(CoerceNoneToDict(), TIER_SCHEMA_BASE),
    }
)

RECORDER_SCHEMA = {
    vol.Optional(
        CONFIG_TIERS,
        default=DEFAULT_RECORDER_TIERS,
        description=DESC_RECORDER_TIERS,
    ): vol.All(
        [TIER_SCHEMA_RECORDER],
        vol.Length(min=1),
    ),
}


def get_snapshots_schema(undefined_defaults=False):
    """Get snapshots schema."""
    return {
        vol.Optional(
            CONFIG_TIERS,
            default=UNDEFINED if undefined_defaults else DEFAULT_SNAPSHOTS_TIERS,
            description=DESC_SNAPSHOTS_TIERS,
        ): vol.All(
            [TIER_SCHEMA_SNAPSHOTS],
            vol.Length(min=1),
        ),
        vol.Optional(
            CONFIG_FACE_RECOGNITION,
            default=UNDEFINED if undefined_defaults else DEFAULT_FACE_RECOGNITION,
            description=DESC_FACE_RECOGNITION,
        ): Maybe(
            {
                vol.Required(CONFIG_TIERS, description=DESC_DOMAIN_TIERS): vol.All(
                    [TIER_SCHEMA_SNAPSHOTS],
                    vol.Length(min=1),
                ),
            }
        ),
        vol.Optional(
            CONFIG_IMAGE_CLASSIFICATION,
            default=UNDEFINED if undefined_defaults else DEFAULT_IMAGE_CLASSIFICATION,
            description=DESC_IMAGE_CLASSIFICATION,
        ): Maybe(
            {
                vol.Required(CONFIG_TIERS, description=DESC_DOMAIN_TIERS): vol.All(
                    [TIER_SCHEMA_SNAPSHOTS],
                    vol.Length(min=1),
                ),
            }
        ),
        vol.Optional(
            CONFIG_OBJECT_DETECTOR,
            default=UNDEFINED if undefined_defaults else DEFAULT_OBJECT_DETECTOR,
            description=DESC_OBJECT_DETECTOR,
        ): Maybe(
            {
                vol.Required(CONFIG_TIERS, description=DESC_DOMAIN_TIERS): vol.All(
                    [TIER_SCHEMA_SNAPSHOTS],
                    vol.Length(min=1),
                ),
            }
        ),
        vol.Optional(
            CONFIG_LICENSE_PLATE_RECOGNITION,
            default=UNDEFINED
            if undefined_defaults
            else DEFAULT_LICENSE_PLATE_RECOGNITION,
            description=DESC_LICENSE_PLATE_RECOGNITION,
        ): Maybe(
            {
                vol.Required(CONFIG_TIERS, description=DESC_DOMAIN_TIERS): vol.All(
                    [TIER_SCHEMA_SNAPSHOTS],
                    vol.Length(min=1),
                ),
            }
        ),
        vol.Optional(
            CONFIG_MOTION_DETECTOR,
            default=UNDEFINED if undefined_defaults else DEFAULT_MOTION_DETECTOR,
            description=DESC_MOTION_DETECTOR,
        ): Maybe(
            {
                vol.Required(CONFIG_TIERS, description=DESC_DOMAIN_TIERS): vol.All(
                    [TIER_SCHEMA_SNAPSHOTS],
                    vol.Length(min=1),
                ),
            }
        ),
    }


TIER_SCHEMA_TIMELAPSE = vol.All(
    TIER_SCHEMA_SNAPSHOTS.extend(
        {
            vol.Optional(
                CONFIG_INTERVAL,
                default=DEFAULT_INTERVAL,
                description=DESC_INTERVAL,
            ): {
                vol.Optional(
                    CONFIG_DAYS,
                    default=DEFAULT_DAYS,
                    description=DESC_INTERVAL_DAYS,
                ): Maybe(vol.Coerce(int)),
                vol.Optional(
                    CONFIG_HOURS,
                    default=DEFAULT_HOURS,
                    description=DESC_INTERVAL_HOURS,
                ): Maybe(vol.Coerce(int)),
                vol.Optional(
                    CONFIG_MINUTES,
                    default=DEFAULT_MINUTES,
                    description=DESC_INTERVAL_MINUTES,
                ): Maybe(vol.Coerce(int)),
                vol.Optional(
                    CONFIG_SECONDS,
                    default=DEFAULT_SECONDS,
                    description=DESC_INTERVAL_SECONDS,
                ): Maybe(vol.Coerce(int)),
            },
        }
    ),
)


def get_timelapse_schema():
    """Get timelapse schema."""
    return {
        vol.Required(CONFIG_TIERS, description=DESC_TIMELAPSE_TIERS): vol.All(
            [TIER_SCHEMA_TIMELAPSE],
            vol.Length(min=1),
        ),
    }
