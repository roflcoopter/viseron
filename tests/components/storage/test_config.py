"""Test storage component config."""

from contextlib import nullcontext
from unittest.mock import Mock, patch

import pytest
import voluptuous as vol

from viseron.components.storage import CONFIG_SCHEMA, validate_tiers
from viseron.components.storage.config import _check_path_exists
from viseron.components.storage.const import (
    DEFAULT_TIER_CHECK_BATCH_SIZE,
    DEFAULT_TIER_CHECK_CPU_LIMIT,
    DEFAULT_TIER_CHECK_SLEEP_BETWEEN_BATCHES,
    DEFAULT_TIER_CHECK_WORKERS,
)


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
        "tier_check_cpu_limit": DEFAULT_TIER_CHECK_CPU_LIMIT,
        "tier_check_batch_size": DEFAULT_TIER_CHECK_BATCH_SIZE,
        "tier_check_sleep_between_batches": DEFAULT_TIER_CHECK_SLEEP_BETWEEN_BATCHES,
        "tier_check_workers": DEFAULT_TIER_CHECK_WORKERS,
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
    # Patch the _check_path_exists function
    with patch("viseron.components.storage.config._check_path_exists"):
        with raises as exc_info:
            _config = validate_tiers(config)

    if error_message and exc_info:
        assert str(exc_info.value) == error_message

    if _config:
        assert _config == config


def test_check_path_exists():
    """Test _check_path_exists."""
    with patch("os.path.exists", return_value=True) as mock_exists:
        _check_path_exists(
            create_tier(
                path="/tier1",
                events={"max_age": {"days": 7}},
            ),
            "recorder",
        )

        mock_exists.reset_mock()

        # Test recorder with custom path
        tier = create_tier(path="/custom/path/")
        _check_path_exists(tier, "recorder")
        mock_exists.assert_called_once_with("/custom/path/")
        mock_exists.reset_mock()

        # Test snapshots with root path
        tier = create_tier_snapshots(path="/")
        _check_path_exists(tier, "snapshots")
        mock_exists.assert_called_once_with("/snapshots")
        mock_exists.reset_mock()

        # Test snapshots with custom path
        tier = create_tier_snapshots(path="/custom/snapshots/")
        _check_path_exists(tier, "snapshots")
        mock_exists.assert_called_once_with("/custom/snapshots/")
        mock_exists.reset_mock()

    # Test error cases when paths don't exist
    mock_exists = Mock(return_value=False)
    with patch("os.path.exists", mock_exists):
        # Test recorder root path error
        tier = create_tier(path="/")
        with pytest.raises(vol.Invalid, match="The /segments folder does not exist"):
            _check_path_exists(tier, "recorder")

        # Test recorder custom path error
        tier = create_tier(path="/custom/path/")
        with pytest.raises(
            vol.Invalid, match="The /custom/path/ folder does not exist"
        ):
            _check_path_exists(tier, "recorder")

        # Test snapshots root path error
        tier = create_tier_snapshots(path="/")
        with pytest.raises(vol.Invalid, match="The /snapshots folder does not exist"):
            _check_path_exists(tier, "snapshots")

        # Test snapshots custom path error
        tier = create_tier_snapshots(path="/custom/snapshots/")
        with pytest.raises(
            vol.Invalid, match="The /custom/snapshots/ folder does not exist"
        ):
            _check_path_exists(tier, "snapshots")
