"""Test storage component."""
# pylint: disable=protected-access
from __future__ import annotations

import copy
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import ANY, Mock, call, patch

import pytest
import voluptuous as vol

from viseron.components.storage import CONFIG_SCHEMA, Storage, _get_tier_config
from viseron.components.storage.const import (
    COMPONENT,
    CONFIG_CHECK_INTERVAL,
    CONFIG_CONTINUOUS,
    CONFIG_DAYS,
    CONFIG_EVENTS,
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
    CONFIG_OBJECT_DETECTOR,
    CONFIG_PATH,
    CONFIG_POLL,
    CONFIG_RECORDER,
    CONFIG_SECONDS,
    CONFIG_SNAPSHOTS,
    CONFIG_TIERS,
    DEFAULT_RECORDER_TIERS,
    DEFAULT_SNAPSHOTS_TIERS,
    TIER_CATEGORY_RECORDER,
    TIER_CATEGORY_SNAPSHOTS,
    TIER_SUBCATEGORY_EVENT_CLIPS,
    TIER_SUBCATEGORY_FACE_RECOGNITION,
    TIER_SUBCATEGORY_LICENSE_PLATE_RECOGNITION,
    TIER_SUBCATEGORY_MOTION_DETECTOR,
    TIER_SUBCATEGORY_OBJECT_DETECTOR,
    TIER_SUBCATEGORY_SEGMENTS,
    TIER_SUBCATEGORY_THUMBNAILS,
)
from viseron.domains.camera.const import CONFIG_STORAGE

from tests.common import MockCamera
from tests.conftest import MockViseron

TIER_CONFIG = {
    CONFIG_RECORDER: {CONFIG_TIERS: DEFAULT_RECORDER_TIERS},
    CONFIG_SNAPSHOTS: {CONFIG_TIERS: DEFAULT_SNAPSHOTS_TIERS},
}


@pytest.mark.parametrize(
    "config, camera_config, expected",
    [
        (  # Test default config
            TIER_CONFIG,
            {
                CONFIG_RECORDER: {
                    CONFIG_CONTINUOUS: {},
                    CONFIG_EVENTS: {},
                },
                CONFIG_STORAGE: None,
            },
            TIER_CONFIG,
        ),
        (  # Test overriding using continuous
            TIER_CONFIG,
            {
                CONFIG_RECORDER: {
                    CONFIG_CONTINUOUS: {CONFIG_MAX_AGE: {CONFIG_DAYS: 123}},
                    CONFIG_EVENTS: {CONFIG_MAX_SIZE: {CONFIG_MB: 1024}},
                },
                CONFIG_STORAGE: None,
            },
            {
                CONFIG_RECORDER: {
                    CONFIG_TIERS: [
                        {
                            CONFIG_CHECK_INTERVAL: {
                                CONFIG_DAYS: 0,
                                CONFIG_HOURS: 0,
                                CONFIG_MINUTES: 1,
                                CONFIG_SECONDS: 0,
                            },
                            CONFIG_CONTINUOUS: {
                                CONFIG_MAX_AGE: {
                                    CONFIG_DAYS: 123,
                                    CONFIG_HOURS: None,
                                    CONFIG_MINUTES: None,
                                },
                                CONFIG_MAX_SIZE: {CONFIG_GB: None, CONFIG_MB: None},
                                CONFIG_MIN_AGE: {
                                    CONFIG_DAYS: None,
                                    CONFIG_HOURS: None,
                                    CONFIG_MINUTES: None,
                                },
                                CONFIG_MIN_SIZE: {CONFIG_GB: None, CONFIG_MB: None},
                            },
                            CONFIG_EVENTS: {
                                CONFIG_MAX_AGE: {
                                    CONFIG_DAYS: None,
                                    CONFIG_HOURS: None,
                                    CONFIG_MINUTES: None,
                                },
                                CONFIG_MAX_SIZE: {CONFIG_GB: None, CONFIG_MB: 1024},
                                CONFIG_MIN_AGE: {
                                    CONFIG_DAYS: None,
                                    CONFIG_HOURS: None,
                                    CONFIG_MINUTES: None,
                                },
                                CONFIG_MIN_SIZE: {CONFIG_GB: None, CONFIG_MB: None},
                            },
                            CONFIG_MOVE_ON_SHUTDOWN: False,
                            CONFIG_PATH: "/",
                            CONFIG_POLL: False,
                        }
                    ]
                },
                CONFIG_SNAPSHOTS: TIER_CONFIG[CONFIG_SNAPSHOTS],
            },
        ),
        (  # Test overriding using tiers
            TIER_CONFIG,
            {
                CONFIG_RECORDER: {
                    CONFIG_CONTINUOUS: {},
                    CONFIG_EVENTS: {},
                },
                CONFIG_STORAGE: {
                    CONFIG_RECORDER: {
                        CONFIG_TIERS: [
                            {
                                CONFIG_PATH: "/test",
                                CONFIG_CONTINUOUS: {CONFIG_MAX_AGE: {CONFIG_DAYS: 123}},
                                CONFIG_EVENTS: {CONFIG_MAX_AGE: {CONFIG_DAYS: 456}},
                                CONFIG_CHECK_INTERVAL: {
                                    CONFIG_SECONDS: 5,
                                },
                            },
                        ]
                    },
                    CONFIG_SNAPSHOTS: vol.UNDEFINED,
                },
            },
            {
                CONFIG_RECORDER: {
                    CONFIG_TIERS: [
                        {
                            CONFIG_CHECK_INTERVAL: {
                                CONFIG_DAYS: 0,
                                CONFIG_HOURS: 0,
                                CONFIG_MINUTES: 0,
                                CONFIG_SECONDS: 5,
                            },
                            CONFIG_CONTINUOUS: {
                                CONFIG_MAX_AGE: {
                                    CONFIG_DAYS: 123,
                                    CONFIG_HOURS: None,
                                    CONFIG_MINUTES: None,
                                },
                                CONFIG_MAX_SIZE: {CONFIG_GB: None, CONFIG_MB: None},
                                CONFIG_MIN_AGE: {
                                    CONFIG_DAYS: None,
                                    CONFIG_HOURS: None,
                                    CONFIG_MINUTES: None,
                                },
                                CONFIG_MIN_SIZE: {CONFIG_GB: None, CONFIG_MB: None},
                            },
                            CONFIG_EVENTS: {
                                CONFIG_MAX_AGE: {
                                    CONFIG_DAYS: 456,
                                    CONFIG_HOURS: None,
                                    CONFIG_MINUTES: None,
                                },
                                CONFIG_MAX_SIZE: {CONFIG_GB: None, CONFIG_MB: None},
                                CONFIG_MIN_AGE: {
                                    CONFIG_DAYS: None,
                                    CONFIG_HOURS: None,
                                    CONFIG_MINUTES: None,
                                },
                                CONFIG_MIN_SIZE: {CONFIG_GB: None, CONFIG_MB: None},
                            },
                            CONFIG_MOVE_ON_SHUTDOWN: False,
                            CONFIG_PATH: "/test/",
                            CONFIG_POLL: False,
                        }
                    ]
                },
                CONFIG_SNAPSHOTS: TIER_CONFIG[CONFIG_SNAPSHOTS],
            },
        ),
        (  # Test overriding snapshots
            TIER_CONFIG,
            {
                CONFIG_RECORDER: {
                    CONFIG_CONTINUOUS: {},
                    CONFIG_EVENTS: {},
                },
                CONFIG_STORAGE: {
                    CONFIG_SNAPSHOTS: {
                        CONFIG_TIERS: [
                            {
                                CONFIG_PATH: "/test",
                                CONFIG_MAX_AGE: {CONFIG_DAYS: 123},
                                CONFIG_CHECK_INTERVAL: {
                                    CONFIG_SECONDS: 5,
                                },
                            },
                        ]
                    },
                    CONFIG_RECORDER: vol.UNDEFINED,
                },
            },
            {
                CONFIG_SNAPSHOTS: {
                    CONFIG_TIERS: [
                        {
                            CONFIG_CHECK_INTERVAL: {
                                CONFIG_DAYS: 0,
                                CONFIG_HOURS: 0,
                                CONFIG_MINUTES: 0,
                                CONFIG_SECONDS: 5,
                            },
                            CONFIG_MAX_AGE: {
                                CONFIG_DAYS: 123,
                                CONFIG_HOURS: None,
                                CONFIG_MINUTES: None,
                            },
                            CONFIG_MAX_SIZE: {CONFIG_GB: None, CONFIG_MB: None},
                            CONFIG_MIN_AGE: {
                                CONFIG_DAYS: None,
                                CONFIG_HOURS: None,
                                CONFIG_MINUTES: None,
                            },
                            CONFIG_MIN_SIZE: {CONFIG_GB: None, CONFIG_MB: None},
                            CONFIG_MOVE_ON_SHUTDOWN: False,
                            CONFIG_PATH: "/test/",
                            CONFIG_POLL: False,
                        }
                    ]
                },
                CONFIG_RECORDER: TIER_CONFIG[CONFIG_RECORDER],
            },
        ),
        (  # Test overriding snapshots domain
            TIER_CONFIG,
            {
                CONFIG_RECORDER: {
                    CONFIG_CONTINUOUS: {},
                    CONFIG_EVENTS: {},
                },
                CONFIG_STORAGE: {
                    CONFIG_SNAPSHOTS: {
                        CONFIG_TIERS: [
                            {
                                CONFIG_PATH: "/test",
                                CONFIG_MAX_AGE: {CONFIG_DAYS: 123},
                                CONFIG_CHECK_INTERVAL: {
                                    CONFIG_SECONDS: 5,
                                },
                            },
                        ],
                        CONFIG_FACE_RECOGNITION: {
                            CONFIG_TIERS: [
                                {
                                    CONFIG_PATH: "/face",
                                    CONFIG_MAX_AGE: {CONFIG_DAYS: 456},
                                },
                            ]
                        },
                        CONFIG_OBJECT_DETECTOR: vol.UNDEFINED,
                    },
                    CONFIG_RECORDER: vol.UNDEFINED,
                },
            },
            {
                CONFIG_SNAPSHOTS: {
                    CONFIG_TIERS: [
                        {
                            CONFIG_CHECK_INTERVAL: {
                                CONFIG_DAYS: 0,
                                CONFIG_HOURS: 0,
                                CONFIG_MINUTES: 0,
                                CONFIG_SECONDS: 5,
                            },
                            CONFIG_MAX_AGE: {
                                CONFIG_DAYS: 123,
                                CONFIG_HOURS: None,
                                CONFIG_MINUTES: None,
                            },
                            CONFIG_MAX_SIZE: {CONFIG_GB: None, CONFIG_MB: None},
                            CONFIG_MIN_AGE: {
                                CONFIG_DAYS: None,
                                CONFIG_HOURS: None,
                                CONFIG_MINUTES: None,
                            },
                            CONFIG_MIN_SIZE: {CONFIG_GB: None, CONFIG_MB: None},
                            CONFIG_MOVE_ON_SHUTDOWN: False,
                            CONFIG_PATH: "/test/",
                            CONFIG_POLL: False,
                        }
                    ],
                    CONFIG_FACE_RECOGNITION: {
                        CONFIG_TIERS: [
                            {
                                CONFIG_PATH: "/face/",
                                CONFIG_CHECK_INTERVAL: {
                                    CONFIG_DAYS: 0,
                                    CONFIG_HOURS: 0,
                                    CONFIG_MINUTES: 1,
                                    CONFIG_SECONDS: 0,
                                },
                                CONFIG_MAX_AGE: {
                                    CONFIG_DAYS: 456,
                                    CONFIG_HOURS: None,
                                    CONFIG_MINUTES: None,
                                },
                                CONFIG_MAX_SIZE: {CONFIG_GB: None, CONFIG_MB: None},
                                CONFIG_MIN_AGE: {
                                    CONFIG_DAYS: None,
                                    CONFIG_HOURS: None,
                                    CONFIG_MINUTES: None,
                                },
                                CONFIG_MIN_SIZE: {CONFIG_GB: None, CONFIG_MB: None},
                                CONFIG_MOVE_ON_SHUTDOWN: False,
                                CONFIG_POLL: False,
                            }
                        ]
                    },
                    CONFIG_OBJECT_DETECTOR: vol.UNDEFINED,
                },
                CONFIG_RECORDER: TIER_CONFIG[CONFIG_RECORDER],
            },
        ),
    ],
)
def test_get_tier_config(config, camera_config, expected) -> None:
    """Test get_tier_config."""
    mocked_camera = MockCamera(config=camera_config)
    assert _get_tier_config(config, mocked_camera) == expected


@pytest.fixture(name="storage", scope="function")
def fixture_storage(vis: MockViseron) -> vol.Generator[Storage, Any, None]:
    """Create a Storage instance."""
    _config = copy.deepcopy(TIER_CONFIG)
    _config[CONFIG_SNAPSHOTS][CONFIG_TIERS].append(
        {
            CONFIG_PATH: "/test",
            CONFIG_MAX_AGE: {CONFIG_DAYS: 123},
        }
    )

    # Create mock classes for tier handlers
    mock_face_recognition_handler = Mock(name="SnapshotTierHandler")
    mock_object_detector_handler = Mock(name="SnapshotTierHandler")
    mock_license_plate_recognition_handler = Mock(name="SnapshotTierHandler")
    mock_motion_detector_handler = Mock(name="SnapshotTierHandler")
    mock_segments_handler = Mock(name="SegmentsTierHandler")
    mock_thumbnail_handler = Mock(name="ThumbnailTierHandler")
    mock_event_clip_handler = Mock(name="EventClipTierHandler")

    # Create patchers for the tier handlers in the TIER_CATEGORIES dictionary
    patched_categories = {
        TIER_CATEGORY_RECORDER: [
            {
                "subcategory": TIER_SUBCATEGORY_SEGMENTS,
                "tier_handler": mock_segments_handler,
            },
            {
                "subcategory": TIER_SUBCATEGORY_EVENT_CLIPS,
                "tier_handler": mock_event_clip_handler,
            },
            {
                "subcategory": TIER_SUBCATEGORY_THUMBNAILS,
                "tier_handler": mock_thumbnail_handler,
            },
        ],
        TIER_CATEGORY_SNAPSHOTS: [
            {
                "subcategory": TIER_SUBCATEGORY_FACE_RECOGNITION,
                "tier_handler": mock_face_recognition_handler,
            },
            {
                "subcategory": TIER_SUBCATEGORY_OBJECT_DETECTOR,
                "tier_handler": mock_object_detector_handler,
            },
            {
                "subcategory": TIER_SUBCATEGORY_LICENSE_PLATE_RECOGNITION,
                "tier_handler": mock_license_plate_recognition_handler,
            },
            {
                "subcategory": TIER_SUBCATEGORY_MOTION_DETECTOR,
                "tier_handler": mock_motion_detector_handler,
            },
        ],
    }

    storage_mocks = {
        TIER_CATEGORY_RECORDER: {
            TIER_SUBCATEGORY_SEGMENTS: mock_segments_handler,
            TIER_SUBCATEGORY_EVENT_CLIPS: mock_event_clip_handler,
            TIER_SUBCATEGORY_THUMBNAILS: mock_thumbnail_handler,
        },
        TIER_CATEGORY_SNAPSHOTS: {
            TIER_SUBCATEGORY_FACE_RECOGNITION: mock_face_recognition_handler,
            TIER_SUBCATEGORY_OBJECT_DETECTOR: mock_object_detector_handler,
            TIER_SUBCATEGORY_LICENSE_PLATE_RECOGNITION: (
                mock_license_plate_recognition_handler
            ),
            TIER_SUBCATEGORY_MOTION_DETECTOR: mock_motion_detector_handler,
        },
    }

    with patch("viseron.components.storage.CleanupManager"), patch(
        "viseron.components.storage.config._check_path_exists"
    ), patch("viseron.components.storage.TIER_CATEGORIES", patched_categories):
        config = CONFIG_SCHEMA({COMPONENT: _config})[COMPONENT]
        _storage = Storage(vis, config)
        _storage._storage_mocks = storage_mocks  # type: ignore[attr-defined]
        yield _storage


class TestStorage:
    """Test the Storage class."""

    def test_search_file(self, storage: Storage) -> None:
        """Test the search_file method."""
        with (
            tempfile.TemporaryDirectory() as tier1,
            tempfile.TemporaryDirectory() as tier2,
        ):
            tier_handler1 = Mock(tier={CONFIG_PATH: f"{tier1}/"})
            tier_handler2 = Mock(tier={CONFIG_PATH: f"{tier2}/"})
            storage._camera_tier_handlers["test_camera"] = {}
            storage._camera_tier_handlers["test_camera"]["test_category"] = []
            storage._camera_tier_handlers["test_camera"]["test_category"].append(
                {"test_subcategory": tier_handler1}
            )
            storage._camera_tier_handlers["test_camera"]["test_category"].append(
                {"test_subcategory": tier_handler2}
            )

            Path(os.path.join(tier1, "test_path")).touch()
            Path(os.path.join(tier2, "test_path")).touch()

            assert storage.search_file(
                "test_camera",
                "test_category",
                "test_subcategory",
                os.path.join(tier1, "test_path"),
            ) == os.path.join(tier2, "test_path")

    def test_create_tier_handlers(self, storage: Storage) -> None:
        """Test create_tier_handlers method."""
        camera = MockCamera(
            config={
                CONFIG_RECORDER: {
                    CONFIG_CONTINUOUS: {},
                    CONFIG_EVENTS: {},
                },
                CONFIG_STORAGE: None,
            }
        )

        storage.create_tier_handlers(camera)
        handlers = storage._camera_tier_handlers[camera.identifier]

        # Verify recorder handlers were created
        assert len(handlers[TIER_CATEGORY_RECORDER]) == 1
        for handler_dict in handlers[TIER_CATEGORY_RECORDER]:
            assert TIER_SUBCATEGORY_SEGMENTS in handler_dict
            assert TIER_SUBCATEGORY_EVENT_CLIPS in handler_dict
            assert TIER_SUBCATEGORY_THUMBNAILS in handler_dict

        subcategories = [
            TIER_SUBCATEGORY_SEGMENTS,
            TIER_SUBCATEGORY_EVENT_CLIPS,
            TIER_SUBCATEGORY_THUMBNAILS,
        ]
        for handler_dict in handlers[TIER_CATEGORY_RECORDER]:
            for subcategory in subcategories:
                assert subcategory in handler_dict

        for subcategory in handlers[TIER_CATEGORY_RECORDER][-1].keys():
            storage._storage_mocks[  # type: ignore[attr-defined]
                TIER_CATEGORY_RECORDER
            ][subcategory].assert_called_once_with(
                storage._vis,
                camera,
                0,
                TIER_CATEGORY_RECORDER,
                subcategory,
                ANY,
                None,
            )

        #
        # Verify snapshots handlers were created
        assert len(handlers[TIER_CATEGORY_SNAPSHOTS]) == 2
        for handler_dict in handlers[TIER_CATEGORY_SNAPSHOTS]:
            assert all(
                subcategory in handler_dict
                for subcategory in storage._storage_mocks[  # type: ignore[attr-defined]
                    TIER_CATEGORY_SNAPSHOTS
                ].keys()
            )

        for subcategory in handlers[TIER_CATEGORY_SNAPSHOTS][-1].keys():
            assert (
                storage._storage_mocks[  # type: ignore[attr-defined]
                    TIER_CATEGORY_SNAPSHOTS
                ][subcategory].call_count
                == 2
            )
            storage._storage_mocks[  # type: ignore[attr-defined]
                TIER_CATEGORY_SNAPSHOTS
            ][subcategory].assert_has_calls(
                [
                    call(
                        storage._vis,
                        camera,
                        0,
                        TIER_CATEGORY_SNAPSHOTS,
                        subcategory,
                        ANY,
                        ANY,
                    ),
                    call(
                        storage._vis,
                        camera,
                        1,
                        TIER_CATEGORY_SNAPSHOTS,
                        subcategory,
                        ANY,
                        None,
                    ),
                ]
            )

        # Test creating handlers for existing camera (should not create new ones)
        original_handlers = storage._camera_tier_handlers[camera.identifier]
        storage.create_tier_handlers(camera)
        assert storage._camera_tier_handlers[camera.identifier] is original_handlers

    def test_create_tier_handlers_custom_config(self, storage: Storage) -> None:
        """Test create_tier_handlers with custom tier config."""
        camera = MockCamera()

        custom_config = {
            CONFIG_RECORDER: {
                CONFIG_TIERS: [
                    {
                        CONFIG_PATH: "/test1/",
                    },
                    {
                        CONFIG_PATH: "/test2/",
                    },
                ]
            },
            CONFIG_SNAPSHOTS: {
                CONFIG_TIERS: [
                    {
                        CONFIG_PATH: "/snap1/",
                    },
                    {
                        CONFIG_PATH: "/snap2/",
                    },
                ]
            },
        }

        with patch(
            "viseron.components.storage._get_tier_config",
            return_value=custom_config,
        ):
            storage.create_tier_handlers(camera)

            # Verify custom paths are used
            assert (
                len(
                    storage._camera_tier_handlers[camera.identifier][
                        TIER_CATEGORY_RECORDER
                    ]
                )
                == 2
            )

            subcategories = [
                TIER_SUBCATEGORY_SEGMENTS,
                TIER_SUBCATEGORY_EVENT_CLIPS,
                TIER_SUBCATEGORY_THUMBNAILS,
            ]
            for subcategory in subcategories:
                storage._storage_mocks[  # type: ignore[attr-defined]
                    TIER_CATEGORY_RECORDER
                ][subcategory].assert_has_calls(
                    [
                        call(
                            storage._vis,
                            camera,
                            0,
                            TIER_CATEGORY_RECORDER,
                            subcategory,
                            custom_config[CONFIG_RECORDER][CONFIG_TIERS][0],
                            custom_config[CONFIG_RECORDER][CONFIG_TIERS][1],
                        ),
                        call(
                            storage._vis,
                            camera,
                            1,
                            TIER_CATEGORY_RECORDER,
                            subcategory,
                            custom_config[CONFIG_RECORDER][CONFIG_TIERS][1],
                            None,
                        ),
                    ]
                )

            for subcategory in storage._storage_mocks[  # type: ignore[attr-defined]
                TIER_CATEGORY_SNAPSHOTS
            ].keys():
                storage._storage_mocks[  # type: ignore[attr-defined]
                    TIER_CATEGORY_SNAPSHOTS
                ][subcategory].assert_has_calls(
                    [
                        call(
                            storage._vis,
                            camera,
                            0,
                            TIER_CATEGORY_SNAPSHOTS,
                            subcategory,
                            custom_config[CONFIG_SNAPSHOTS][CONFIG_TIERS][0],
                            custom_config[CONFIG_SNAPSHOTS][CONFIG_TIERS][1],
                        ),
                        call(
                            storage._vis,
                            camera,
                            1,
                            TIER_CATEGORY_SNAPSHOTS,
                            subcategory,
                            custom_config[CONFIG_SNAPSHOTS][CONFIG_TIERS][1],
                            None,
                        ),
                    ]
                )

    def test_create_tier_handlers_domain_override(self, storage: Storage) -> None:
        """Test create_tier_handlers with domain override."""
        camera = MockCamera()

        custom_config: dict[str, Any] = {
            CONFIG_RECORDER: {CONFIG_TIERS: []},
            CONFIG_SNAPSHOTS: {
                CONFIG_TIERS: [
                    {
                        CONFIG_PATH: "/snap1/",
                    },
                    {
                        CONFIG_PATH: "/snap2/",
                    },
                ],
                CONFIG_FACE_RECOGNITION: {
                    CONFIG_TIERS: [
                        {
                            CONFIG_PATH: "/face1/",
                        },
                        {
                            CONFIG_PATH: "/face2/",
                        },
                    ]
                },
            },
        }

        with patch(
            "viseron.components.storage._get_tier_config",
            return_value=custom_config,
        ):
            storage.create_tier_handlers(camera)

            storage._storage_mocks[  # type: ignore[attr-defined]
                TIER_CATEGORY_SNAPSHOTS
            ][TIER_SUBCATEGORY_OBJECT_DETECTOR].assert_has_calls(
                [
                    call(
                        storage._vis,
                        camera,
                        0,
                        TIER_CATEGORY_SNAPSHOTS,
                        TIER_SUBCATEGORY_OBJECT_DETECTOR,
                        custom_config[CONFIG_SNAPSHOTS][CONFIG_TIERS][0],
                        custom_config[CONFIG_SNAPSHOTS][CONFIG_TIERS][1],
                    ),
                    call(
                        storage._vis,
                        camera,
                        1,
                        TIER_CATEGORY_SNAPSHOTS,
                        TIER_SUBCATEGORY_OBJECT_DETECTOR,
                        custom_config[CONFIG_SNAPSHOTS][CONFIG_TIERS][1],
                        None,
                    ),
                ]
            )

            storage._storage_mocks[  # type: ignore[attr-defined]
                TIER_CATEGORY_SNAPSHOTS
            ][TIER_SUBCATEGORY_FACE_RECOGNITION].assert_has_calls(
                [
                    call(
                        storage._vis,
                        camera,
                        0,
                        TIER_CATEGORY_SNAPSHOTS,
                        TIER_SUBCATEGORY_FACE_RECOGNITION,
                        custom_config[CONFIG_SNAPSHOTS][CONFIG_FACE_RECOGNITION][
                            CONFIG_TIERS
                        ][0],
                        custom_config[CONFIG_SNAPSHOTS][CONFIG_FACE_RECOGNITION][
                            CONFIG_TIERS
                        ][1],
                    ),
                    call(
                        storage._vis,
                        camera,
                        1,
                        TIER_CATEGORY_SNAPSHOTS,
                        TIER_SUBCATEGORY_FACE_RECOGNITION,
                        custom_config[CONFIG_SNAPSHOTS][CONFIG_FACE_RECOGNITION][
                            CONFIG_TIERS
                        ][1],
                        None,
                    ),
                ]
            )
