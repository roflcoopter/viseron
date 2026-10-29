"""Tests for viseron.components.gstreamer.gst_process."""

from __future__ import annotations

import logging
import pickle

from viseron.components.gstreamer import gst_process, stream


def _config(**overrides):
    defaults = {
        "camera_identifier": "cam",
        "alias": "gstreamer_cam",
        "pipeline": "videotestsrc ! fakesink",
        "gst_loglevel": "warning",
        "temp_segments_folder": "/tmp/segments",
        "extension": "mp4",
        "sensitive_strings": ("hunter2",),
        "log_level": logging.INFO,
    }
    defaults.update(overrides)
    return gst_process.GstProcessConfig(**defaults)


def test_config_is_picklable() -> None:
    """The payload crosses a forkserver boundary, so it must pickle.

    In particular gst_loglevel must be the config string and not a Gst.DebugLevel.
    """
    config = _config()
    assert pickle.loads(pickle.dumps(config))  # noqa: S301 == config


def test_segment_location_uses_temp_folder_and_extension() -> None:
    """Segment paths come from the payload."""
    location = gst_process.segment_location(_config())
    assert location.startswith("/tmp/segments/")
    assert location.endswith(".mp4")


def test_gst_logger_names_matches_the_parent_stream_loggers() -> None:
    """The child must configure the levels of the loggers the parent named."""
    assert gst_process.gst_logger_names("cam") == (
        f"{stream.__name__}.cam",
        f"{stream.__name__}.cam.gstreamer",
    )
