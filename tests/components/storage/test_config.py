"""Test storage component config."""

from contextlib import nullcontext

import pytest
import voluptuous as vol

from viseron.components.storage import CONFIG_SCHEMA, validate_tiers


def create_time_config(days=None, hours=None, minutes=None):
    """Create a standardized time configuration."""
    return {
        "days": days,
        "hours": hours,
        "minutes": minutes,
    }


def create_size_config(gb=None, mb=None):
    """Create a standardized size configuration."""
    return {
        "gb": gb,
        "mb": mb,
    }


def create_check_interval(days=0, hours=0, minutes=1, seconds=0):
    """Create a standardized check interval configuration."""
    return {
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds,
    }


def create_retain_config(max_age=None, min_age=None, max_size=None, min_size=None):
    """Create a standardized configuration for retention rules."""
    return {
        "max_age": create_time_config(
            **(max_age or {"days": None, "hours": None, "minutes": None})
        ),
        "min_age": create_time_config(
            **(min_age or {"days": None, "hours": None, "minutes": None})
        ),
        "max_size": create_size_config(**(max_size or {"gb": None, "mb": None})),
        "min_size": create_size_config(**(min_size or {"gb": None, "mb": None})),
    }


def create_tier(
    path="/",
    events=None,
    continuous=None,
    move_on_shutdown=False,
    poll=False,
    check_interval=None,
):
    """Create a standardized tier configuration."""
    return {
        "path": path,
        "events": create_retain_config(**(events or {})),
        "continuous": create_retain_config(**(continuous or {})),
        "move_on_shutdown": move_on_shutdown,
        "poll": poll,
        "check_interval": create_check_interval(**(check_interval or {})),
    }


def create_tier_snapshots(
    path="/",
    move_on_shutdown=False,
    poll=False,
    check_interval=None,
    max_age=None,
    min_age=None,
    max_size=None,
    min_size=None,
):
    """Create a standardized tier configuration for snapshots."""
    return {
        "path": path,
        "move_on_shutdown": move_on_shutdown,
        "poll": poll,
        "check_interval": create_check_interval(**(check_interval or {})),
        **create_retain_config(
            max_age=max_age, min_age=min_age, max_size=max_size, min_size=min_size
        ),
    }


DEFAULT_CONFIG = {
    "storage": {
        "recorder": {"tiers": [create_tier(events={"max_age": {"days": 7}})]},
        "snapshots": {
            "tiers": [
                {
                    "path": "/",
                    **create_retain_config(max_age={"days": 7}),
                    "move_on_shutdown": False,
                    "poll": False,
                    "check_interval": create_check_interval(),
                }
            ],
            "face_recognition": None,
            "license_plate_recognition": None,
            "motion_detector": None,
            "object_detector": None,
        },
    },
}


@pytest.mark.parametrize(
    "config",
    [
        {"storage": {}},
    ],
)
def test_config_schema(config) -> None:
    """Test config schema."""
    assert CONFIG_SCHEMA(config) == DEFAULT_CONFIG


TEST_CASES = [
    # Valid configuration with two tiers
    (
        {
            "storage": {
                "recorder": {
                    "tiers": [
                        create_tier(
                            path="/tier1",
                            events={"max_age": {"days": 7}},
                        ),
                        create_tier(
                            path="/tier2",
                            events={"max_age": {"days": 14}},
                        ),
                    ]
                }
            }
        },
        nullcontext(),
        None,
    ),
    # Reserved path error
    (
        {
            "storage": {
                "recorder": {
                    "tiers": [
                        create_tier(
                            path="/tmp",
                            events={"max_age": {"days": 7}},
                        ),
                    ]
                }
            }
        },
        pytest.raises(vol.Invalid),
        "Tier /tmp is a reserved path and cannot be used",
    ),
    # Duplicate path error
    (
        {
            "storage": {
                "recorder": {
                    "tiers": [
                        create_tier(
                            path="/tier1",
                            events={"max_age": {"days": 7}},
                        ),
                        create_tier(
                            path="/tier1",
                            events={"max_age": {"days": 14}},
                        ),
                    ]
                }
            }
        },
        pytest.raises(vol.Invalid),
        "Tier /tier1 is defined multiple times",
    ),
    # Invalid max_age progression
    (
        {
            "storage": {
                "recorder": {
                    "tiers": [
                        create_tier(
                            path="/tier1",
                            events={"max_age": {"days": 7}},
                        ),
                        create_tier(
                            path="/tier2",
                            events={"max_age": {"hours": 168}},
                        ),
                    ]
                }
            }
        },
        pytest.raises(vol.Invalid),
        "Tier /tier2 max_age must be greater than previous tier max_age",
    ),
    # Events not enabled in first tier
    (
        {
            "storage": {
                "recorder": {
                    "tiers": [
                        create_tier(
                            path="/tier1",
                            continuous={"max_age": {"days": 7}},
                        ),
                        create_tier(
                            path="/tier2",
                            events={"max_age": {"hours": 168}},
                        ),
                    ]
                }
            }
        },
        pytest.raises(vol.Invalid),
        "Event recordings is not enabled in the first tier and thus cannot be "
        "enabled in any subsequent tier",
    ),
    # Continuous not enabled in first tier
    (
        {
            "storage": {
                "recorder": {
                    "tiers": [
                        create_tier(
                            path="/tier1",
                            events={"max_age": {"days": 7}},
                        ),
                        create_tier(
                            path="/tier2",
                            events={"max_age": {"hours": 168}},
                            continuous={"max_age": {"hours": 168}},
                        ),
                    ]
                }
            }
        },
        pytest.raises(vol.Invalid),
        "Continuous recordings is not enabled in the first tier and thus cannot be "
        "enabled in any subsequent tier",
    ),
    # Snapshot domain overrides
    (
        {
            "storage": {
                "recorder": DEFAULT_CONFIG["storage"]["recorder"],
                "snapshots": {
                    "tiers": [
                        create_tier_snapshots(
                            path="/snap1",
                            max_age={"days": 7},
                        ),
                        create_tier_snapshots(
                            path="/snap2",
                            max_age={"days": 14},
                        ),
                    ],
                    "face_recognition": {
                        "tiers": [
                            create_tier_snapshots(
                                path="/snap1",
                                max_age={"days": 7},
                            ),
                            create_tier_snapshots(
                                path="/snap2",
                                max_age={"days": 14},
                            ),
                        ],
                    },
                },
            },
        },
        nullcontext(),
        None,
    ),
]


@pytest.mark.parametrize("config, raises, error_message", TEST_CASES)
def test_validate_tiers(config, raises, error_message):
    """Test validate_tiers."""
    _config = None
    with raises as exc_info:
        _config = validate_tiers(config)

    if error_message and exc_info:
        assert str(exc_info.value) == error_message

    if _config:
        assert _config == config
