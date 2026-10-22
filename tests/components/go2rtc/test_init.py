"""Tests for go2rtc consumers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from viseron.components.go2rtc import CONFIG_SCHEMA, setup
from viseron.components.onvif.utils import extract_rtsp_from_go2rtc
from viseron.helpers.config_validation import validate_config


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({}, None),
        ({"streams": {}}, None),
        ({"streams": {"front": "rtsp://camera/live"}}, "rtsp://camera/live"),
        (
            {"streams": {"front": ["ffmpeg:camera", "rtsp://camera/live"]}},
            "rtsp://camera/live",
        ),
    ],
)
def test_onvif_stream_lookup(
    tmp_path: Path, options: dict[str, Any], expected: str | None
) -> None:
    """ONVIF can read the configuration stored by the migrated component."""
    vis = Mock(data={})
    camera = Mock(_vis=vis, identifier="front")
    with (
        patch("viseron.components.go2rtc.GO2RTC_CONFIG", str(tmp_path / "go2rtc.yaml")),
        patch("viseron.components.go2rtc.Go2RTC.restart"),
    ):
        assert setup(vis, validate_config(CONFIG_SCHEMA, {"go2rtc": options}))
    assert extract_rtsp_from_go2rtc(camera) == expected
