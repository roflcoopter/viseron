"""Tests for object_detector config."""

import pytest
import voluptuous as vol

from viseron.domains.object_detector import CAMERA_SCHEMA


@pytest.mark.parametrize("value", [0, 0.0, "0"])
def test_camera_schema_rejects_zero_fps(value):
    """Test that fps 0 is rejected.

    FrameScanner.calculate_scan_interval divides output_fps by the
    configured fps, so a validator-accepted 0 crashed NVR setup with
    ZeroDivisionError.
    """
    with pytest.raises(vol.Invalid):
        CAMERA_SCHEMA({"fps": value})


def test_camera_schema_accepts_positive_fps():
    """Test that positive fractional fps values are still accepted."""
    assert CAMERA_SCHEMA({"fps": 0.5})["fps"] == 0.5
    assert CAMERA_SCHEMA({})["fps"] == 1
