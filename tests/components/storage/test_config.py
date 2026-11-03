"""Tests for the config of the storage component."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock, patch

import pytest
import voluptuous as vol
from pydantic_core import PydanticCustomError

from viseron.components.storage import CONFIG_SCHEMA
from viseron.components.storage.config import (
    MaxAge,
    MaxSize,
    SnapshotsConfig,
    StorageRoot,
    TierRetention,
    _check_path_exists,
    validate_tiers,
)
from viseron.helpers.config_validation import ConfigValidationError, validate_config
from viseron.helpers.validators import UNDEFINED

if TYPE_CHECKING:
    from collections.abc import Iterator

EVERY_KEY = {
    "storage": {
        "tier_check_cpu_limit": 20,
        "tier_check_workers": 2,
        "tier_check_batch_size": 10,
        "tier_check_sleep_between_batches": 1.5,
        "recorder": {
            "tiers": [
                {
                    "path": "/recorder",
                    "poll": True,
                    "move_on_shutdown": True,
                    "drain": True,
                    "check_interval": {
                        "days": 1,
                        "hours": 2,
                        "minutes": 3,
                        "seconds": 4,
                    },
                    "continuous": {
                        "min_size": {"gb": 1, "mb": 2},
                        "max_size": {"gb": 3, "mb": 4},
                        "max_age": {"days": 1, "hours": 2, "minutes": 3},
                        "min_age": {"days": 0, "hours": 1, "minutes": 2},
                    },
                    "events": {
                        "min_size": {"gb": 1, "mb": 2},
                        "max_size": {"gb": 3, "mb": 4},
                        "max_age": {"days": 1, "hours": 2, "minutes": 3},
                        "min_age": {"days": 0, "hours": 1, "minutes": 2},
                    },
                }
            ]
        },
        "snapshots": {
            "tiers": [
                {
                    "path": "/snapshots",
                    "poll": True,
                    "move_on_shutdown": True,
                    "drain": True,
                    "check_interval": {"seconds": 30},
                    "min_size": {"gb": 1, "mb": 2},
                    "max_size": {"gb": 3, "mb": 4},
                    "max_age": {"days": 1, "hours": 2, "minutes": 3},
                    "min_age": {"days": 0, "hours": 1, "minutes": 2},
                }
            ],
            "face_recognition": {"tiers": [{"path": "/face_recognition"}]},
            "image_classification": {"tiers": [{"path": "/image_classification"}]},
            "object_detector": {"tiers": [{"path": "/object_detector"}]},
            "license_plate_recognition": {
                "tiers": [{"path": "/license_plate_recognition"}]
            },
            "motion_detector": {"tiers": [{"path": "/motion_detector"}]},
        },
        "timelapse": {
            "tiers": [
                {
                    "path": "/timelapse",
                    "poll": True,
                    "move_on_shutdown": True,
                    "drain": True,
                    "check_interval": {"minutes": 5},
                    "min_size": {"gb": 1},
                    "max_size": {"mb": 4},
                    "max_age": {"days": 1},
                    "min_age": {"hours": 1},
                    "interval": {"days": 0, "hours": 0, "minutes": 1, "seconds": 5},
                }
            ]
        },
    }
}

ACCEPTED = [
    pytest.param(EVERY_KEY, id="every_key"),
    pytest.param(
        {
            "storage": {
                "recorder": {
                    "tiers": [
                        {
                            "path": "/ssd/tier1",
                            "events": {"max_age": {"days": 1}},
                            "continuous": {"max_age": {"days": 1}},
                        },
                        {"path": "/hdd/tier2", "events": {"max_age": {"days": 7}}},
                    ]
                },
                "snapshots": {
                    "tiers": [{"path": "/config/tier1", "max_age": {"days": 1}}]
                },
            }
        },
        id="docs_example",
    ),
    pytest.param(
        {
            "storage": {
                "recorder": {
                    "tiers": [{"path": "/", "continuous": {"max_size": {"gb": 10}}}]
                }
            }
        },
        id="docs_continuous_example",
    ),
    pytest.param(
        {
            "storage": {
                "recorder": {
                    "tiers": [
                        {
                            "path": "/mnt/ramdisk",
                            "move_on_shutdown": True,
                            "continuous": {
                                "max_size": {"gb": 1},
                                "max_age": {"days": 1},
                            },
                            "events": {"max_size": {"gb": 1}, "max_age": {"days": 1}},
                        },
                        {
                            "path": "/mnt/ssd",
                            "events": {
                                "min_size": {"gb": 1},
                                "max_size": {"gb": 10},
                                "max_age": {"days": 7},
                            },
                        },
                        {
                            "path": "/mnt/nas",
                            "events": {
                                "min_age": {"days": 30},
                                "max_size": {"gb": 100},
                            },
                        },
                    ]
                }
            }
        },
        id="docs_advanced_example",
    ),
    pytest.param(
        {
            "storage": {
                "recorder": {
                    "tiers": [
                        {
                            "path": "/",
                            "events": {"max_age": {"days": 14}},
                            "continuous": {"max_size": {"gb": 10}},
                        }
                    ]
                }
            }
        },
        id="docs_recordings_example",
    ),
    pytest.param(
        {"storage": {"snapshots": {"tiers": [{"path": "/", "max_size": {"gb": 1}}]}}},
        id="docs_snapshots_example",
    ),
    pytest.param(
        {
            "storage": {
                "snapshots": {
                    "face_recognition": {
                        "tiers": [{"path": "/", "max_size": {"gb": 1}}]
                    },
                    "license_plate_recognition": {
                        "tiers": [{"path": "/", "max_age": {"days": 14}}]
                    },
                }
            }
        },
        id="docs_snapshot_domains_example",
    ),
    pytest.param(
        {
            "storage": {
                "timelapse": {
                    "tiers": [
                        {
                            "path": "/config/timelapse",
                            "interval": {"minutes": 1},
                            "max_age": {"days": 7},
                        },
                        {
                            "path": "/mnt/nas/timelapse",
                            "interval": {"minutes": 15},
                            "max_age": {"days": 365},
                        },
                    ]
                }
            }
        },
        id="docs_timelapse_example",
    ),
    pytest.param({"storage": {"tier_check_workers": 1}}, id="workers_min"),
    pytest.param(
        {
            "storage": {
                "recorder": {"tiers": [{"path": "/", "check_interval": {"days": 0}}]}
            }
        },
        id="check_interval_min",
    ),
]

REJECTED = [
    pytest.param({"storage": {"tier_check_workers": 0}}, id="workers_below_range"),
    pytest.param(
        {
            "storage": {
                "recorder": {"tiers": [{"path": "/", "check_interval": {"days": -1}}]}
            }
        },
        id="check_interval_below_range",
    ),
    pytest.param({"storage": {"recorder": {"tiers": []}}}, id="no_recorder_tiers"),
    pytest.param({"storage": {"snapshots": {"tiers": []}}}, id="no_snapshots_tiers"),
    pytest.param(
        {"storage": {"snapshots": {"face_recognition": {"tiers": []}}}},
        id="no_domain_tiers",
    ),
    pytest.param({"storage": {"timelapse": {"tiers": []}}}, id="no_timelapse_tiers"),
    pytest.param(
        {"storage": {"snapshots": {"tiers": [{"path": ""}]}}}, id="empty_path"
    ),
]


@pytest.fixture(autouse=True)
def fixture_paths_exist() -> Iterator[Mock]:
    """Make every tier path exist."""
    with patch(
        "viseron.components.storage.config.os.path.exists", return_value=True
    ) as mock_exists:
        yield mock_exists


@pytest.mark.parametrize("config", ACCEPTED)
def test_config_is_accepted(config: dict) -> None:
    """A valid config passes validation."""
    validate_config(CONFIG_SCHEMA, config)


@pytest.mark.parametrize("config", REJECTED)
def test_config_is_rejected(config: dict) -> None:
    """A config that is not valid fails validation."""
    with pytest.raises(ConfigValidationError):
        validate_config(CONFIG_SCHEMA, config)


DEFAULT_RETENTION = {
    "min_size": {"gb": None, "mb": None},
    "max_size": {"gb": None, "mb": None},
    "max_age": {"days": None, "hours": None, "minutes": None},
    "min_age": {"days": None, "hours": None, "minutes": None},
}
DEFAULT_TIER = {
    "path": "/",
    "poll": False,
    "move_on_shutdown": False,
    "drain": False,
    "check_interval": {"days": 0, "hours": 0, "minutes": 1, "seconds": 0},
}


def test_defaults() -> None:
    """A storage without config gets the default tiers."""
    validated: StorageRoot = validate_config(CONFIG_SCHEMA, {})
    assert validated.storage.model_dump() == {
        "tier_check_cpu_limit": 10,
        "tier_check_workers": 4,
        "tier_check_batch_size": 5,
        "tier_check_sleep_between_batches": 0.5,
        "recorder": {
            "tiers": [
                {
                    **DEFAULT_TIER,
                    "continuous": DEFAULT_RETENTION,
                    "events": {
                        **DEFAULT_RETENTION,
                        "max_age": {"days": 7, "hours": None, "minutes": None},
                    },
                }
            ]
        },
        "snapshots": {
            "tiers": [
                {
                    **DEFAULT_RETENTION,
                    **DEFAULT_TIER,
                    "max_age": {"days": 7, "hours": None, "minutes": None},
                }
            ],
            "face_recognition": None,
            "image_classification": None,
            "object_detector": None,
            "license_plate_recognition": None,
            "motion_detector": None,
        },
        "timelapse": None,
    }


def test_check_interval_null_is_zero() -> None:
    """A check_interval without keys is zero, not the default of one minute."""
    validated: StorageRoot = validate_config(
        CONFIG_SCHEMA,
        {"storage": {"recorder": {"tiers": [{"path": "/", "check_interval": None}]}}},
    )
    check_interval = validated.storage.recorder.tiers[0].check_interval
    assert check_interval.to_timedelta() == timedelta(0)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param("/", "/", id="root"),
        pytest.param("/mnt/ssd", "/mnt/ssd/", id="without_slash"),
        pytest.param("/mnt/ssd/", "/mnt/ssd/", id="with_slash"),
    ],
)
def test_path_ends_with_slash(path: str, expected: str) -> None:
    """A tier path always ends with a slash."""
    validated: StorageRoot = validate_config(
        CONFIG_SCHEMA, {"storage": {"snapshots": {"tiers": [{"path": path}]}}}
    )
    assert validated.storage.snapshots.tiers[0].path == expected


def _recorder(*tiers: dict[str, Any]) -> dict[str, Any]:
    return {"storage": {"recorder": {"tiers": list(tiers)}}}


def _snapshots(*tiers: dict[str, Any]) -> dict[str, Any]:
    return {"storage": {"snapshots": {"tiers": list(tiers)}}}


@pytest.mark.parametrize(
    ("config", "message"),
    [
        pytest.param(
            _snapshots({"path": "/tier1"}, {"path": "/tier1/"}),
            "storage.snapshots: Tier /tier1/ is defined multiple times",
            id="duplicate_path",
        ),
        pytest.param(
            _snapshots(
                {"path": "/tier1", "max_age": {"days": 7}},
                {"path": "/tier2", "max_age": {"hours": 168}},
            ),
            "storage.snapshots: Tier /tier2/ max_age must be greater than previous "
            "tier max_age",
            id="max_age_not_increasing",
        ),
        pytest.param(
            {
                "storage": {
                    "snapshots": {
                        "face_recognition": {
                            "tiers": [{"path": "/tier1"}, {"path": "/tier1"}]
                        }
                    }
                }
            },
            "storage.snapshots: Tier /tier1/ is defined multiple times",
            id="duplicate_path_in_domain",
        ),
        pytest.param(
            {
                "storage": {
                    "timelapse": {"tiers": [{"path": "/tier1"}, {"path": "/tier1"}]}
                }
            },
            "storage.timelapse: Tier /tier1/ is defined multiple times",
            id="duplicate_path_in_timelapse",
        ),
        pytest.param(
            _recorder(
                {"path": "/tier1", "events": {"max_age": {"days": 7}}},
                {"path": "/tier2", "events": {"max_age": {"hours": 168}}},
            ),
            "storage.recorder: Tier /tier2/ max_age must be greater than previous "
            "tier max_age",
            id="events_max_age_not_increasing",
        ),
        pytest.param(
            _recorder(
                {"path": "/tier1", "continuous": {"max_age": {"days": 7}}},
                {"path": "/tier2", "events": {"max_age": {"days": 14}}},
            ),
            "storage.recorder: Event recordings is not enabled in the first tier and "
            "thus cannot be enabled in any subsequent tier",
            id="events_not_in_first_tier",
        ),
        pytest.param(
            _recorder(
                {"path": "/tier1", "events": {"max_age": {"days": 7}}},
                {
                    "path": "/tier2",
                    "events": {"max_age": {"days": 14}},
                    "continuous": {"max_age": {"days": 14}},
                },
            ),
            "storage.recorder: Continuous recordings is not enabled in the first tier "
            "and thus cannot be enabled in any subsequent tier",
            id="continuous_not_in_first_tier",
        ),
    ],
)
def test_tier_rules(config: dict[str, Any], message: str) -> None:
    """Tiers that break a rule are rejected with a message naming the tier."""
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(CONFIG_SCHEMA, config)
    assert str(exc_info.value) == message


@pytest.mark.parametrize(
    "config",
    [
        pytest.param(
            _snapshots({"path": "/tier1", "max_age": {"days": 7}}, {"path": "/tier2"}),
            id="last_tier_without_max_age",
        ),
        pytest.param(
            _recorder(
                {
                    "path": "/tier1",
                    "events": {"max_age": {"days": 7}},
                    "continuous": {"max_age": {"days": 1}},
                },
                {"path": "/tier2", "events": {"max_age": {"days": 14}}},
            ),
            id="events_and_continuous_age_separately",
        ),
        pytest.param(
            {
                "storage": {
                    "snapshots": {
                        "tiers": [{"path": "/tier1"}],
                        "face_recognition": {"tiers": [{"path": "/tier1"}]},
                    }
                }
            },
            id="domain_checked_on_its_own",
        ),
    ],
)
def test_tier_rules_allow(config: dict[str, Any]) -> None:
    """Tiers that follow the rules are accepted."""
    validate_config(CONFIG_SCHEMA, config)


@pytest.mark.parametrize(
    "path",
    [
        "/tmp",
        "/tmp/",
        "/tmp//",
        "/tmp/./",
        "/tmp/../tmp",
        "/tmp/viseron",
        "/tmp/viseron/",
        "/tmp/viseron//",
    ],
)
def test_reserved_path(path: str) -> None:
    """A reserved path cannot be used as a tier, however it is written."""
    with pytest.raises(ConfigValidationError, match="is a reserved path"):
        validate_config(CONFIG_SCHEMA, _snapshots({"path": path}))


@pytest.mark.parametrize(
    ("path", "category", "checked"),
    [
        pytest.param(
            "/",
            "recorder",
            ["/segments", "/event_clips", "/thumbnails"],
            id="recorder_root",
        ),
        pytest.param("/", "snapshots", ["/snapshots"], id="snapshots_root"),
        pytest.param("/", "timelapse", ["/timelapse"], id="timelapse_root"),
        pytest.param("/custom/", "recorder", ["/custom/"], id="custom_path"),
    ],
)
def test_check_path_exists(
    fixture_paths_exist: Mock, path: str, category: str, checked: list[str]
) -> None:
    """The folders of a tier have to be mounted."""
    _check_path_exists(path, category)
    assert [call.args[0] for call in fixture_paths_exist.call_args_list] == checked

    fixture_paths_exist.return_value = False
    with pytest.raises(
        PydanticCustomError,
        match=f"The {checked[0]} folder does not exist. Please mount it",
    ):
        _check_path_exists(path, category)


def test_missing_path_rejects_config(fixture_paths_exist: Mock) -> None:
    """A config with a tier path that does not exist is rejected."""
    fixture_paths_exist.return_value = False
    with pytest.raises(
        ConfigValidationError, match="The /mnt/ssd/ folder does not exist"
    ):
        validate_config(CONFIG_SCHEMA, _snapshots({"path": "/mnt/ssd"}))


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        pytest.param({"mb": 1}, 1048576, id="mb"),
        pytest.param({"gb": 1}, 1073741824, id="gb"),
        pytest.param({"mb": 0, "gb": 2}, 2147483648, id="mb_zero"),
        pytest.param({"mb": 2, "gb": 2}, 2097152 + 2147483648, id="added"),
        pytest.param({"mb": 0.5}, 524288, id="fraction"),
    ],
)
def test_size_to_bytes(size: dict[str, float], expected: int) -> None:
    """Gigabytes and megabytes are added together."""
    assert MaxSize.model_validate(size).to_bytes() == expected


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        pytest.param({"minutes": 1}, 60, id="minutes"),
        pytest.param({"days": 1}, 86400, id="days"),
        pytest.param({"hours": 1}, 3600, id="hours"),
        pytest.param({"minutes": 1, "days": 1, "hours": 1}, 90060, id="added"),
    ],
)
def test_age_to_timedelta(age: dict[str, int], expected: int) -> None:
    """Days, hours and minutes are added together."""
    assert MaxAge.model_validate(age).to_timedelta().total_seconds() == expected


def test_retention_enabled() -> None:
    """Retention is enabled when any of its rules is set."""
    assert not TierRetention().enabled
    assert TierRetention.model_validate({"min_age": {"minutes": 1}}).enabled
    assert TierRetention.model_validate({"max_size": {"mb": 1}}).enabled


def test_domain_tiers() -> None:
    """A domain without tiers of its own uses the common snapshot tiers."""
    snapshots = SnapshotsConfig.model_validate(
        {
            "tiers": [{"path": "/common"}],
            "face_recognition": {"tiers": [{"path": "/face"}]},
        }
    )
    assert snapshots.domain_tiers("face_recognition")[0].path == "/face/"
    assert snapshots.domain_tiers("object_detector")[0].path == "/common/"
    assert [tiers[0].path for tiers in snapshots.tier_lists()] == ["/common/", "/face/"]


def test_validate_camera_tiers() -> None:
    """Tiers that a camera sets are checked with the same rules."""
    validate_tiers(
        {
            "storage": {
                "recorder": UNDEFINED(),
                "snapshots": {
                    "tiers": [{"path": "/tier1/"}],
                    "face_recognition": UNDEFINED(),
                },
                "timelapse": None,
            }
        }
    )

    with pytest.raises(vol.Invalid, match="Tier /tier1/ is defined multiple times"):
        validate_tiers(
            {
                "storage": {
                    "recorder": {"tiers": [{"path": "/tier1/"}, {"path": "/tier1/"}]},
                    "snapshots": UNDEFINED(),
                    "timelapse": UNDEFINED(),
                }
            }
        )

    with pytest.raises(vol.Invalid, match="Tier /tmp/ is a reserved path"):
        validate_tiers(
            {
                "storage": {
                    "recorder": UNDEFINED(),
                    "snapshots": {"tiers": [{"path": "/tmp/"}]},
                    "timelapse": UNDEFINED(),
                }
            }
        )
