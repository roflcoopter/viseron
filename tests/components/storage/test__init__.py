"""Test storage component."""


import pprint
from contextlib import nullcontext

import pytest
import voluptuous as vol

from viseron.components.storage import CONFIG_SCHEMA, validate_tiers
from viseron.components.storage.const import CONFIG_RECORDINGS, CONFIG_TIERS

DEFAULT_CONFIG = {
    "storage": {
        "recordings": {
            "create_event_clip": False,
            "tiers": [
                {
                    "path": "/",
                    "max_age": {"hours": None, "minutes": None, "days": 7},
                    "min_age": {"minutes": None, "days": None, "hours": None},
                    "min_size": {"mb": None, "gb": None},
                    "max_size": {"mb": None, "gb": None},
                    "move_on_shutdown": False,
                    "poll": False,
                }
            ],
            "type": "events",
        },
        "snapshots": {
            "tiers": [
                {
                    "path": "/",
                    "max_age": {"hours": None, "minutes": None, "days": 7},
                    "min_age": {"minutes": None, "days": None, "hours": None},
                    "min_size": {"mb": None, "gb": None},
                    "max_size": {"mb": None, "gb": None},
                    "move_on_shutdown": False,
                    "poll": False,
                }
            ],
            "face_recognition": None,
            "object_detection": None,
        },
    }
}


@pytest.mark.parametrize(
    "config",
    [
        {"storage": {}},
    ],
)
def test_config_schema(config) -> None:
    """Test config schema."""
    pprint.pprint(CONFIG_SCHEMA(config))
    assert CONFIG_SCHEMA(config) == DEFAULT_CONFIG


@pytest.mark.parametrize(
    "config, raises",
    [
        (
            {
                "storage": {
                    CONFIG_RECORDINGS: {
                        CONFIG_TIERS: [
                            {
                                "path": "/tier1",
                                "max_age": {"hours": None, "minutes": None, "days": 7},
                            },
                            {
                                "path": "/tier2",
                                "max_age": {"hours": None, "minutes": None, "days": 14},
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
                    CONFIG_RECORDINGS: {
                        CONFIG_TIERS: [
                            {
                                "path": "/tmp",
                                "max_age": {"hours": None, "minutes": None, "days": 7},
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
                    CONFIG_RECORDINGS: {
                        CONFIG_TIERS: [
                            {
                                "path": "/tier1",
                                "max_age": {"hours": None, "minutes": None, "days": 7},
                            },
                            {
                                "path": "/tier1",
                                "max_age": {"hours": None, "minutes": None, "days": 14},
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
                    CONFIG_RECORDINGS: {
                        CONFIG_TIERS: [
                            {
                                "path": "/tier1",
                                "max_age": {"hours": None, "minutes": None, "days": 7},
                            },
                            {
                                "path": "/tier2",
                                "max_age": {
                                    "hours": 168,
                                    "minutes": None,
                                    "days": None,
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
