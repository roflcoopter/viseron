"""Tests for the logger component."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from viseron.components.logger import (
    _get_loggers_for_camera,
    _matches_camera_override,
    setup,
    unload,
)
from viseron.components.logger.const import (
    COMPONENT,
    CONFIG_CAMERAS,
    CONFIG_DEFAULT_LEVEL,
    CONFIG_LOGS,
    PREVIOUS_CONFIG,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def _cleanup_logging() -> Generator[None, Any, None]:
    """Save and restore logging state around each test."""
    original_class = logging.getLoggerClass()
    # Snapshot logger names created before the test
    existing_loggers = set(logging.Logger.manager.loggerDict.keys())
    yield
    # Restore the original logger class
    logging.setLoggerClass(original_class)
    # Remove any loggers created during the test
    for name in list(logging.Logger.manager.loggerDict.keys()):
        if name not in existing_loggers:
            del logging.Logger.manager.loggerDict[name]
    # Reset root logger level
    logging.getLogger("").setLevel(logging.WARNING)


def _make_vis() -> MagicMock:
    """Create a minimal mock Viseron with a real data dict."""
    vis = MagicMock()
    vis.data = {}
    return vis


def _make_config(
    default_level: str = "info",
    logs: dict[str, str] | None = None,
    cameras: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a validated config dict for the logger component."""
    component_config: dict[str, Any] = {
        CONFIG_DEFAULT_LEVEL: default_level,
        CONFIG_CAMERAS: cameras or {},
    }
    if logs is not None:
        component_config[CONFIG_LOGS] = logs
    return {COMPONENT: component_config}


class TestSetupFirstRun:
    """Tests for initial setup (no previous config)."""

    def test_creates_data_structure(self):
        """setup() creates the expected vis.data[COMPONENT] structure."""
        vis = _make_vis()
        config = _make_config(default_level="warning")
        setup(vis, config)

        assert COMPONENT in vis.data
        assert CONFIG_LOGS in vis.data[COMPONENT]
        assert CONFIG_CAMERAS in vis.data[COMPONENT]
        assert CONFIG_DEFAULT_LEVEL in vis.data[COMPONENT]
        assert vis.data[COMPONENT][CONFIG_DEFAULT_LEVEL] == "warning"

    def test_sets_default_log_level(self):
        """setup() sets the root logger to the configured default level."""
        vis = _make_vis()
        config = _make_config(default_level="debug")
        setup(vis, config)

        assert logging.getLogger("").level == logging.DEBUG

    def test_sets_log_overrides(self):
        """setup() applies log overrides from config."""
        vis = _make_vis()
        config = _make_config(logs={"test.logger.a": "debug", "test.logger.b": "error"})
        setup(vis, config)

        assert vis.data[COMPONENT][CONFIG_LOGS] == {
            "test.logger.a": "debug",
            "test.logger.b": "error",
        }
        assert logging.getLogger("test.logger.a").level == logging.DEBUG
        assert logging.getLogger("test.logger.b").level == logging.ERROR

    def test_stores_camera_overrides(self):
        """setup() stores camera overrides in vis.data for ViseronLogger."""
        vis = _make_vis()
        config = _make_config(cameras={"my_camera": "warning"})
        setup(vis, config)

        assert vis.data[COMPONENT][CONFIG_CAMERAS] == {"my_camera": "warning"}

    def test_sets_logger_class(self):
        """setup() sets ViseronLogger as the logging class."""
        vis = _make_vis()
        config = _make_config()
        setup(vis, config)

        logger_class = logging.getLoggerClass()
        assert logger_class.__name__ == "ViseronLogger"

    def test_camera_override_on_new_logger(self):
        """Test that new loggers matching a camera override gets correct level."""
        vis = _make_vis()
        config = _make_config(cameras={"test_cam": "error"})
        setup(vis, config)

        logger = logging.getLogger("viseron.components.ffmpeg.test_cam.stream")
        assert logger.level == logging.ERROR


class TestUnload:
    """Tests for unload()."""

    def test_snapshots_config(self):
        """unload() stores a snapshot of the current config."""
        vis = _make_vis()
        config = _make_config(
            default_level="debug",
            logs={"test.a": "warning"},
            cameras={"cam1": "error"},
        )
        setup(vis, config)
        unload(vis)

        previous = vis.data[COMPONENT][PREVIOUS_CONFIG]
        assert previous[CONFIG_DEFAULT_LEVEL] == "debug"
        assert previous[CONFIG_LOGS] == {"test.a": "warning"}
        assert previous[CONFIG_CAMERAS] == {"cam1": "error"}

    def test_snapshot_is_a_copy(self):
        """The snapshot dicts are copies, not the same objects."""
        vis = _make_vis()
        config = _make_config(logs={"test.x": "debug"}, cameras={"cam": "info"})
        setup(vis, config)
        unload(vis)

        previous = vis.data[COMPONENT][PREVIOUS_CONFIG]
        assert previous[CONFIG_LOGS] is not vis.data[COMPONENT][CONFIG_LOGS]
        assert previous[CONFIG_CAMERAS] is not vis.data[COMPONENT][CONFIG_CAMERAS]

    def test_does_not_reset_log_levels(self):
        """unload() should not reset any log levels to avoid "gaps" when reloading."""
        vis = _make_vis()
        config = _make_config(
            default_level="debug", logs={"test.unload_check": "error"}
        )
        setup(vis, config)
        unload(vis)

        # Root logger keeps the debug level
        assert logging.getLogger("").level == logging.DEBUG
        # Specific override is still active
        assert logging.getLogger("test.unload_check").level == logging.ERROR

    def test_preserves_vis_data_component(self):
        """unload() does not delete vis.data[COMPONENT]."""
        vis = _make_vis()
        setup(vis, _make_config())
        unload(vis)

        assert COMPONENT in vis.data


class TestReload:
    """Tests for reloading with changed config."""

    def _setup_and_reload(
        self,
        initial_config: dict[str, Any],
        new_config: dict[str, Any],
    ) -> MagicMock:
        """Call setup, unload, and setup again with new config."""
        vis = _make_vis()
        setup(vis, initial_config)
        unload(vis)
        setup(vis, new_config)
        return vis

    def test_reuses_same_dict_objects(self):
        """On reload, the CONFIG_LOGS and CONFIG_CAMERAS dicts are the same objects."""
        vis = _make_vis()
        config = _make_config()
        setup(vis, config)

        log_dict_id = id(vis.data[COMPONENT][CONFIG_LOGS])
        cam_dict_id = id(vis.data[COMPONENT][CONFIG_CAMERAS])

        unload(vis)
        setup(vis, _make_config(logs={"new.logger": "debug"}))

        assert id(vis.data[COMPONENT][CONFIG_LOGS]) == log_dict_id
        assert id(vis.data[COMPONENT][CONFIG_CAMERAS]) == cam_dict_id

    def test_does_not_call_set_logger_class_again(self):
        """On reload, logging.setLoggerClass is NOT called again."""
        vis = _make_vis()
        with patch("logging.setLoggerClass") as mock_set_logger_class:
            setup(vis, _make_config())
            mock_set_logger_class.assert_called_once()

        original_class = logging.getLoggerClass()

        unload(vis)

        with patch("logging.setLoggerClass") as mock_set_logger_class:
            setup(vis, _make_config())
            mock_set_logger_class.assert_not_called()
        assert logging.getLoggerClass() is original_class

    def test_previous_config_cleaned_up(self):
        """After reload, PREVIOUS_CONFIG is removed from vis.data."""
        vis = self._setup_and_reload(_make_config(), _make_config())
        assert PREVIOUS_CONFIG not in vis.data[COMPONENT]

    def test_default_level_changed(self):
        """Changing default_level updates the root logger."""
        vis = self._setup_and_reload(
            _make_config(default_level="info"),
            _make_config(default_level="debug"),
        )
        assert logging.getLogger("").level == logging.DEBUG
        assert vis.data[COMPONENT][CONFIG_DEFAULT_LEVEL] == "debug"

    def test_add_log_override(self):
        """Adding a new log override sets the level on that logger."""
        vis = self._setup_and_reload(
            _make_config(),
            _make_config(logs={"test.reload.add": "debug"}),
        )
        assert logging.getLogger("test.reload.add").level == logging.DEBUG
        assert vis.data[COMPONENT][CONFIG_LOGS] == {"test.reload.add": "debug"}

    def test_remove_log_override(self):
        """Removing a log override resets the logger to NOTSET."""
        vis = self._setup_and_reload(
            _make_config(logs={"test.reload.remove": "debug"}),
            _make_config(logs={}),
        )
        assert logging.getLogger("test.reload.remove").level == logging.NOTSET
        assert "test.reload.remove" not in vis.data[COMPONENT][CONFIG_LOGS]

    def test_change_log_override_level(self):
        """Changing a log override level updates the logger."""
        vis = self._setup_and_reload(
            _make_config(logs={"test.reload.change": "debug"}),
            _make_config(logs={"test.reload.change": "error"}),
        )
        assert logging.getLogger("test.reload.change").level == logging.ERROR
        assert vis.data[COMPONENT][CONFIG_LOGS]["test.reload.change"] == "error"

    def test_add_camera_override(self):
        """Adding a camera override sets level on matching existing loggers."""
        vis = _make_vis()
        setup(vis, _make_config())
        cam_logger = logging.getLogger("viseron.components.ffmpeg.newcam.stream")

        unload(vis)
        setup(vis, _make_config(cameras={"newcam": "error"}))

        assert cam_logger.level == logging.ERROR
        assert vis.data[COMPONENT][CONFIG_CAMERAS] == {"newcam": "error"}

    def test_remove_camera_override(self):
        """Removing a camera override resets matching loggers to NOTSET."""
        vis = _make_vis()
        setup(vis, _make_config(cameras={"oldcam": "error"}))
        cam_logger = logging.getLogger("viseron.components.ffmpeg.oldcam.stream")
        assert cam_logger.level == logging.ERROR

        unload(vis)
        setup(vis, _make_config(cameras={}))

        assert cam_logger.level == logging.NOTSET
        assert "oldcam" not in vis.data[COMPONENT][CONFIG_CAMERAS]

    def test_change_camera_override_level(self):
        """Changing a camera override level updates matching loggers."""
        vis = _make_vis()
        setup(vis, _make_config(cameras={"cam_change": "error"}))
        cam_logger = logging.getLogger("viseron.components.ffmpeg.cam_change.detector")
        assert cam_logger.level == logging.ERROR

        unload(vis)
        setup(vis, _make_config(cameras={"cam_change": "debug"}))

        assert cam_logger.level == logging.DEBUG

    def test_removed_camera_falls_back_to_log_override(self):
        """When camera override is removed, a log override takes effect."""
        vis = _make_vis()
        logger_name = "viseron.components.ffmpeg.fallback_cam.stream"
        setup(
            vis,
            _make_config(
                logs={logger_name: "warning"},
                cameras={"fallback_cam": "error"},
            ),
        )
        cam_logger = logging.getLogger(logger_name)
        assert cam_logger.level == logging.ERROR

        unload(vis)
        setup(
            vis,
            _make_config(
                logs={logger_name: "warning"},
                cameras={},
            ),
        )

        assert cam_logger.level == logging.WARNING

    def test_unchanged_camera_override_not_touched(self):
        """Unchanged camera overrides leave matching loggers alone."""
        vis = _make_vis()
        setup(
            vis,
            _make_config(cameras={"stable_cam": "warning", "gone_cam": "debug"}),
        )
        stable = logging.getLogger("viseron.comp.stable_cam.x")
        gone = logging.getLogger("viseron.comp.gone_cam.x")
        assert stable.level == logging.WARNING
        assert gone.level == logging.DEBUG

        unload(vis)
        setup(vis, _make_config(cameras={"stable_cam": "warning"}))

        # Stable camera logger untouched
        assert stable.level == logging.WARNING
        # Removed camera logger reset
        assert gone.level == logging.NOTSET

    def test_reload_with_no_logs_section(self):
        """Reload from config with logs to config without logs section."""
        vis = _make_vis()
        setup(vis, _make_config(logs={"test.comp.nologs": "debug"}))
        assert logging.getLogger("test.comp.nologs").level == logging.DEBUG

        unload(vis)
        # New config has no logs key
        setup(vis, {COMPONENT: {CONFIG_DEFAULT_LEVEL: "info", CONFIG_CAMERAS: {}}})

        assert logging.getLogger("test.comp.nologs").level == logging.NOTSET

    def test_reload_with_empty_cameras(self):
        """Reload where cameras goes from populated to empty."""
        vis = _make_vis()
        setup(vis, _make_config(cameras={"cam_empty": "error"}))
        logger = logging.getLogger("viseron.components.ffmpeg.cam_empty.detector")
        assert logger.level == logging.ERROR

        unload(vis)
        setup(vis, _make_config(cameras={}))
        assert logger.level == logging.NOTSET

    def test_multiple_reloads(self):
        """Multiple consecutive reload cycles work correctly."""
        vis = _make_vis()
        setup(vis, _make_config(logs={"test.multi": "debug"}))
        logger = logging.getLogger("test.multi")
        assert logger.level == logging.DEBUG

        # First reload: change level
        unload(vis)
        setup(vis, _make_config(logs={"test.multi": "warning"}))
        assert logger.level == logging.WARNING

        # Second reload: remove override
        unload(vis)
        setup(vis, _make_config(logs={}))
        assert logger.level == logging.NOTSET

        # Third reload: add it back
        unload(vis)
        setup(vis, _make_config(logs={"test.multi": "error"}))
        assert logger.level == logging.ERROR


class TestViseronLoggerAfterReload:
    """Test that ViseronLogger setLevel protection works after reload."""

    def test_setlevel_blocked_for_new_log_override(self):
        """After adding a log override via reload, setLevel is blocked."""
        vis = _make_vis()
        setup(vis, _make_config())

        unload(vis)
        setup(vis, _make_config(logs={"test.blocked": "debug"}))

        logger = logging.getLogger("test.blocked")
        assert logger.level == logging.DEBUG

        # External setLevel call should be blocked
        logger.setLevel(logging.CRITICAL)
        assert logger.level == logging.DEBUG

    def test_setlevel_unblocked_for_removed_log_override(self):
        """After removing a log override via reload, setLevel works again."""
        vis = _make_vis()
        setup(vis, _make_config(logs={"test.unblocked": "debug"}))
        logger = logging.getLogger("test.unblocked")

        unload(vis)
        setup(vis, _make_config(logs={}))

        # Now setLevel should work
        logger.setLevel(logging.CRITICAL)
        assert logger.level == logging.CRITICAL

    def test_setlevel_blocked_for_new_camera_override(self):
        """After adding camera override via reload, setLevel is blocked."""
        vis = _make_vis()
        setup(vis, _make_config())
        logger = logging.getLogger("viseron.comp.blocked_cam.test")

        unload(vis)
        setup(vis, _make_config(cameras={"blocked_cam": "warning"}))

        logger.setLevel(logging.DEBUG)
        assert logger.level == logging.WARNING

    def test_setlevel_unblocked_for_removed_camera_override(self):
        """After removing camera override via reload, setLevel works."""
        vis = _make_vis()
        setup(vis, _make_config(cameras={"freed_cam": "warning"}))
        logger = logging.getLogger("viseron.comp.freed_cam.test")

        unload(vis)
        setup(vis, _make_config(cameras={}))

        logger.setLevel(logging.DEBUG)
        assert logger.level == logging.DEBUG


class TestHelpers:
    """Tests for internal helper functions."""

    def test_matches_camera_override_positive(self):
        """Returns True when logger name contains a camera ID piece."""
        assert _matches_camera_override(
            "viseron.components.ffmpeg.my_cam.stream", {"my_cam": "debug"}
        )

    def test_matches_camera_override_negative(self):
        """Returns False when no piece matches."""
        assert not _matches_camera_override(
            "viseron.components.ffmpeg.other.stream", {"my_cam": "debug"}
        )

    def test_matches_camera_override_partial_no_match(self):
        """Partial substring match within a piece does not count."""
        assert not _matches_camera_override(
            "viseron.components.my_camera_extended", {"my_camera": "debug"}
        )

    def test_get_loggers_for_camera(self):
        """Returns only loggers whose name contains the camera ID as a piece."""
        vis = _make_vis()
        setup(vis, _make_config())

        match1 = logging.getLogger("viseron.comp.test_find_cam.a")
        match2 = logging.getLogger("viseron.comp.test_find_cam.b")
        no_match = logging.getLogger("viseron.comp.other_cam.c")

        result = _get_loggers_for_camera("test_find_cam")
        assert match1 in result
        assert match2 in result
        assert no_match not in result
