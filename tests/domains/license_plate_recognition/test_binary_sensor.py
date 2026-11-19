"""Tests for the license plate recognition binary sensor."""

from __future__ import annotations

from types import SimpleNamespace

from viseron.domains.license_plate_recognition.binary_sensor import (
    LicensePlateRecognitionBinarySensor,
)

from tests.common import MockCamera

CAMERA_IDENTIFIER = "test_camera"


def test_extra_attributes_are_returned(vis) -> None:
    """extra_attributes builds a dict and must return it."""
    sensor = LicensePlateRecognitionBinarySensor(
        vis, MockCamera(identifier=CAMERA_IDENTIFIER), "abc123"
    )
    sensor._detected = True
    sensor._result = SimpleNamespace(confidence=0.87)

    attributes = sensor.extra_attributes

    assert attributes["plate"] == "abc123"
    assert attributes["detected"] is True
    assert attributes["confidence"] == 0.87
