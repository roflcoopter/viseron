"""Test storage component."""
# pylint: disable=protected-access
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, patch

import pytest

from viseron.components.storage import Storage, _get_tier_config
from viseron.components.storage.const import (
    CONFIG_CHECK_INTERVAL,
    CONFIG_CONTINUOUS,
    CONFIG_DAYS,
    CONFIG_EVENTS,
    CONFIG_HOURS,
    CONFIG_MINUTES,
    CONFIG_MOVE_ON_SHUTDOWN,
    CONFIG_PATH,
    CONFIG_POLL,
    CONFIG_RECORDER,
    CONFIG_SECONDS,
    CONFIG_SNAPSHOTS,
    CONFIG_TIERS,
    DEFAULT_RECORDER_TIERS,
)
from viseron.domains.camera.const import CONFIG_STORAGE

from tests.common import MockCamera

if TYPE_CHECKING:
    from viseron import Viseron

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
                                CONFIG_CHECK_INTERVAL: {
                                    CONFIG_DAYS: 0,
                                    CONFIG_HOURS: 0,
                                    CONFIG_MINUTES: 0,
                                    CONFIG_SECONDS: 0,
                                },
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
                            CONFIG_CHECK_INTERVAL: {
                                CONFIG_DAYS: 0,
                                CONFIG_HOURS: 0,
                                CONFIG_MINUTES: 0,
                                CONFIG_SECONDS: 0,
                            },
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


class TestStorage:
    """Test the Storage class."""

    def setup_method(self, vis: Viseron) -> None:
        """Set up the test."""
        with patch("viseron.components.storage.CleanupManager"):
            self._storage = Storage(vis, MagicMock())

    def test_search_file(self) -> None:
        """Test the search_file method."""
        with tempfile.TemporaryDirectory() as tier1, tempfile.TemporaryDirectory() as tier2:  # pylint: disable=line-too-long
            tier_handler1 = Mock(tier={CONFIG_PATH: f"{tier1}/"})
            tier_handler2 = Mock(tier={CONFIG_PATH: f"{tier2}/"})
            self._storage._camera_tier_handlers["test_camera"] = {}
            self._storage._camera_tier_handlers["test_camera"]["test_category"] = []
            self._storage._camera_tier_handlers["test_camera"]["test_category"].append(
                {"test_subcategory": tier_handler1}
            )
            self._storage._camera_tier_handlers["test_camera"]["test_category"].append(
                {"test_subcategory": tier_handler2}
            )

            Path(os.path.join(tier1, "test_path")).touch()
            Path(os.path.join(tier2, "test_path")).touch()

            assert self._storage.search_file(
                "test_camera",
                "test_category",
                "test_subcategory",
                os.path.join(tier1, "test_path"),
            ) == os.path.join(tier2, "test_path")
