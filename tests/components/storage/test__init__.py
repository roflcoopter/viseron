"""Test storage component."""

from __future__ import annotations

import pytest

from viseron.components.storage import _get_tier_config
from viseron.components.storage.const import (
    CONFIG_CONTINUOUS,
    CONFIG_EVENTS,
    CONFIG_MOVE_ON_SHUTDOWN,
    CONFIG_PATH,
    CONFIG_POLL,
    CONFIG_RECORDER,
    CONFIG_SNAPSHOTS,
    CONFIG_TIERS,
    DEFAULT_RECORDER_TIERS,
)
from viseron.domains.camera.const import CONFIG_STORAGE

from tests.common import MockCamera

CONFIG = {
    CONFIG_RECORDER: {CONFIG_TIERS: DEFAULT_RECORDER_TIERS},
    CONFIG_SNAPSHOTS: {"test": "test"},
}


@pytest.mark.parametrize(
    "config, camera_config, expected",
    [
        (  # Test default config
            CONFIG,
            {
                CONFIG_RECORDER: {
                    CONFIG_CONTINUOUS: {},
                    CONFIG_EVENTS: {},
                    CONFIG_STORAGE: {},
                },
            },
            CONFIG,
        ),
        (  # Test overriding using events/continuous
            CONFIG,
            {
                CONFIG_RECORDER: {
                    CONFIG_CONTINUOUS: {"test": 123},
                    CONFIG_EVENTS: {"test": 456},
                    CONFIG_STORAGE: {},
                }
            },
            {
                CONFIG_RECORDER: {
                    CONFIG_TIERS: [
                        {
                            CONFIG_PATH: "/",
                            CONFIG_CONTINUOUS: {"test": 123},
                            CONFIG_EVENTS: {"test": 456},
                            CONFIG_MOVE_ON_SHUTDOWN: False,
                            CONFIG_POLL: False,
                        },
                    ]
                },
                CONFIG_SNAPSHOTS: CONFIG[CONFIG_SNAPSHOTS],
            },
        ),
        (  # Test overriding using tiers
            CONFIG,
            {
                CONFIG_RECORDER: {
                    CONFIG_CONTINUOUS: {},
                    CONFIG_EVENTS: {},
                    CONFIG_STORAGE: {
                        CONFIG_TIERS: [
                            {
                                CONFIG_PATH: "/test",
                                CONFIG_CONTINUOUS: {"test": 123},
                                CONFIG_EVENTS: {"test": 456},
                            },
                        ]
                    },
                }
            },
            {
                CONFIG_RECORDER: {
                    CONFIG_TIERS: [
                        {
                            CONFIG_PATH: "/test",
                            CONFIG_CONTINUOUS: {"test": 123},
                            CONFIG_EVENTS: {"test": 456},
                        },
                    ]
                },
                CONFIG_SNAPSHOTS: CONFIG[CONFIG_SNAPSHOTS],
            },
        ),
    ],
)
def test_get_tier_config(config, camera_config, expected) -> None:
    """Test get_tier_config."""
    mocked_camera = MockCamera(config=camera_config)
    assert _get_tier_config(config, mocked_camera) == expected
