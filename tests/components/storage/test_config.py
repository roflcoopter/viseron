"""Test storage component config."""

from contextlib import nullcontext

import pytest
import voluptuous as vol

from viseron.components.storage import CONFIG_SCHEMA, validate_tiers

DEFAULT_CONFIG = {
    "storage": {
        "recorder": {
            "create_event_clip": False,
            "tiers": [
                {
                    "path": "/",
                    "events": {
                        "max_age": {"days": 7, "hours": None, "minutes": None},
                        "min_age": {"hours": None, "days": None, "minutes": None},
                        "min_size": {"gb": None, "mb": None},
                        "max_size": {"gb": None, "mb": None},
                    },
                    "move_on_shutdown": False,
                    "poll": False,
                    "continuous": {
                        "min_age": {"minutes": None, "hours": None, "days": None},
                        "max_size": {"gb": None, "mb": None},
                        "max_age": {"minutes": None, "hours": None, "days": None},
                        "min_size": {"gb": None, "mb": None},
                    },
                }
            ],
        },
        "snapshots": {
            "tiers": [
                {
                    "path": "/",
                    "max_age": {"days": 7, "hours": None, "minutes": None},
                    "min_age": {"hours": None, "days": None, "minutes": None},
                    "min_size": {"gb": None, "mb": None},
                    "max_size": {"gb": None, "mb": None},
                    "move_on_shutdown": False,
                    "poll": False,
                }
            ],
            "face_recognition": None,
            "object_detection": None,
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


@pytest.mark.parametrize(
    "config, raises",
    [
        (
            {
                "storage": {
                    "recorder": {
                        "tiers": [
                            {
                                "path": "/tier1",
                                "events": {
                                    "max_age": {
                                        "hours": None,
                                        "minutes": None,
                                        "days": 7,
                                    },
                                },
                            },
                            {
                                "path": "/tier2",
                                "events": {
                                    "max_age": {
                                        "hours": None,
                                        "minutes": None,
                                        "days": 14,
                                    },
                                },
                            },
                        ]
                    },
                }
            },
            nullcontext(),
        ),
        (
            {
                "storage": {
                    "recorder": {
                        "tiers": [
                            {
                                "path": "/tmp",
                                "events": {
                                    "max_age": {
                                        "hours": None,
                                        "minutes": None,
                                        "days": 7,
                                    },
                                },
                            },
                        ]
                    },
                }
            },
            pytest.raises(
                vol.Invalid, match="Tier /tmp is a reserved path and cannot be used"
            ),
        ),
        (
            {
                "storage": {
                    "recorder": {
                        "tiers": [
                            {
                                "path": "/tier1",
                                "events": {
                                    "max_age": {
                                        "hours": None,
                                        "minutes": None,
                                        "days": 7,
                                    },
                                },
                            },
                            {
                                "path": "/tier1",
                                "events": {
                                    "max_age": {
                                        "hours": None,
                                        "minutes": None,
                                        "days": 14,
                                    },
                                },
                            },
                        ]
                    },
                }
            },
            pytest.raises(vol.Invalid, match="Tier /tier1 is defined multiple times"),
        ),
        (
            {
                "storage": {
                    "recorder": {
                        "tiers": [
                            {
                                "path": "/tier1",
                                "events": {
                                    "max_age": {
                                        "hours": None,
                                        "minutes": None,
                                        "days": 7,
                                    },
                                },
                            },
                            {
                                "path": "/tier2",
                                "events": {
                                    "max_age": {
                                        "hours": 168,
                                        "minutes": None,
                                        "days": None,
                                    },
                                },
                            },
                        ]
                    },
                }
            },
            pytest.raises(
                vol.Invalid,
                match="Tier /tier2 max_age must be greater than previous tier max_age",
            ),
        ),
    ],
)
def test_validate_tiers(config, raises):
    """Test validate_tiers."""
    _config = None
    with raises:
        _config = validate_tiers(config)

    if _config:
        assert _config == config
