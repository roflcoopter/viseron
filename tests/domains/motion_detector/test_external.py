"""Tests for AbstractMotionDetectorExternal."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

from viseron.domains.motion_detector import AbstractMotionDetectorExternal
from viseron.domains.motion_detector.const import (
    CONFIG_CAMERAS,
    CONFIG_MAX_MOTION_DURATION,
    CONFIG_MAX_RECORDER_KEEPALIVE,
    CONFIG_RECORDER_KEEPALIVE,
    CONFIG_TRIGGER_EVENT_RECORDING,
)

from tests.common import MockCamera, MockComponent

if TYPE_CHECKING:
    from tests.conftest import MockViseron


CAMERA_IDENTIFIER = "test_camera"
COMPONENT = "test_external_motion_detector"


class ConcreteExternal(AbstractMotionDetectorExternal):
    """Concrete subclass for testing the abstract base."""


@pytest.fixture(name="_setup_camera")
def fixture_setup_camera(vis: MockViseron) -> MockCamera:
    """Register a camera and the test component."""
    MockComponent(vis, COMPONENT)
    return MockCamera(vis, identifier=CAMERA_IDENTIFIER)


def _config(max_motion_duration: int = 0) -> dict:
    return {
        CONFIG_CAMERAS: {
            CAMERA_IDENTIFIER: {
                CONFIG_TRIGGER_EVENT_RECORDING: True,
                CONFIG_RECORDER_KEEPALIVE: False,
                CONFIG_MAX_RECORDER_KEEPALIVE: 0,
                CONFIG_MAX_MOTION_DURATION: max_motion_duration,
            }
        }
    }


@pytest.mark.usefixtures("_setup_camera")
def test_set_motion_detected_on_then_off(
    vis: MockViseron,
) -> None:
    """Toggling motion on then off must dispatch events and update state."""
    detector = ConcreteExternal(vis, COMPONENT, _config(), CAMERA_IDENTIFIER)

    detector.set_motion_detected(True)
    assert detector.motion_detected is True

    detector.set_motion_detected(False)
    assert detector.motion_detected is False


@pytest.mark.usefixtures("_setup_camera")
def test_set_motion_detected_repeated_on_is_idempotent(
    vis: MockViseron,
) -> None:
    """Setting motion to the same value should not duplicate database inserts."""
    detector = ConcreteExternal(vis, COMPONENT, _config(), CAMERA_IDENTIFIER)
    detector.set_motion_detected(True)
    first_id = detector._motion_id
    detector.set_motion_detected(True)
    assert detector._motion_id == first_id


@pytest.mark.usefixtures("_setup_camera")
def test_safety_timer_clears_motion(
    vis: MockViseron,
) -> None:
    """The safety timer should auto-clear motion after max_motion_duration."""
    # A very small duration keeps the test fast.
    detector = ConcreteExternal(
        vis, COMPONENT, _config(max_motion_duration=1), CAMERA_IDENTIFIER
    )
    # Replace duration with a small float so we don't sleep too long.
    detector._max_motion_duration = 0.05  # type: ignore[assignment]
    detector.set_motion_detected(True)
    assert detector.motion_detected is True

    # Wait for the timer to fire.
    deadline = time.monotonic() + 1.0
    while detector.motion_detected and time.monotonic() < deadline:
        time.sleep(0.01)
    assert detector.motion_detected is False


@pytest.mark.usefixtures("_setup_camera")
def test_stop_cancels_safety_timer(
    vis: MockViseron,
) -> None:
    """stop() must cancel any pending safety timer."""
    detector = ConcreteExternal(
        vis, COMPONENT, _config(max_motion_duration=10), CAMERA_IDENTIFIER
    )
    detector.set_motion_detected(True)
    timer = detector._safety_timer
    assert timer is not None
    assert timer.is_alive()
    detector.stop()
    assert detector._safety_timer is None
    timer.join(timeout=1.0)
    assert not timer.is_alive()


@pytest.mark.usefixtures("_setup_camera")
def test_no_safety_timer_when_max_duration_zero(
    vis: MockViseron,
) -> None:
    """A max_motion_duration of 0 disables the safety timer."""
    detector = ConcreteExternal(
        vis, COMPONENT, _config(max_motion_duration=0), CAMERA_IDENTIFIER
    )
    detector.set_motion_detected(True)
    assert detector._safety_timer is None
