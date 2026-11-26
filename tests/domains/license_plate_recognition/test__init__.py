"""Tests for AbstractLicensePlateRecognition."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar
from threading import Event, Timer as RealTimer
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from viseron.domains.license_plate_recognition import (
    AbstractLicensePlateRecognition,
    DetectedLicensePlate,
)
from viseron.domains.license_plate_recognition.const import (
    CONFIG_EXPIRE_AFTER,
    CONFIG_KNOWN_PLATES,
    CONFIG_MIN_CONFIDENCE,
    CONFIG_SAVE_PLATES,
    EVENT_PLATE_EXPIRED,
)
from viseron.domains.post_processor import PostProcessorFrame
from viseron.domains.post_processor.const import (
    CONFIG_CAMERAS,
    CONFIG_LABELS,
    CONFIG_MASK,
)
from viseron.viseron_types import SnapshotDomain

from tests.common import MockCamera, MockComponent

if TYPE_CHECKING:
    from collections.abc import Iterator

    import numpy.typing as npt

    from tests.conftest import MockViseron

CAMERA_IDENTIFIER = "test_camera"
COMPONENT = "test_lpr"
PLATE = "ABC123"


class ControlledTimer(RealTimer):
    """Real timer with a short interval whose callback parks on a hold gate.

    Lets a test let the timer fire for real (so the callback runs in the
    timer's own thread) while controlling exactly when the callback proceeds.
    """

    instances: ClassVar[list[ControlledTimer]] = []

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(0.05, *args[1:], **kwargs)
        self.daemon = True
        self.pre_gate = Event()  # set once the callback was entered
        self.hold = Event()  # callback waits on this
        self._wrapped_function = self.function
        self.function = self._gated_function
        self.instances.append(self)

    def _gated_function(self, *args, **kwargs):
        self.pre_gate.set()
        self.hold.wait(timeout=5)
        return self._wrapped_function(*args, **kwargs)

    def release(self) -> None:
        """Let the parked callback proceed to completion."""
        self.hold.set()
        self.join(timeout=5)


class ConcreteLPR(AbstractLicensePlateRecognition):
    """Concrete implementation for testing."""

    domain = "license_plate_recognition"
    snapshot_domain = SnapshotDomain.LICENSE_PLATE_RECOGNITION

    def __post_init__(self, *args, **kwargs) -> None:
        """Post init hook."""

    def preprocess(self, frame: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
        """Return the frame unchanged."""
        return frame

    def license_plate_recognition(
        self, post_processor_frame: PostProcessorFrame
    ) -> list[DetectedLicensePlate]:
        """Return one fixed plate detection."""
        return [
            DetectedLicensePlate(
                plate=PLATE,
                confidence=0.9,
                rel_x1=0.0,
                rel_y1=0.0,
                rel_x2=0.5,
                rel_y2=0.5,
                detected_object=MagicMock(),
            )
        ]


@pytest.fixture(autouse=True)
def patch_threads() -> Iterator[None]:
    """Patch RestartableThread and reset the controlled timer registry."""
    with patch(
        "viseron.domains.post_processor.RestartableThread", autospec=True
    ) as mock_thread_cls:
        mock_thread_cls.return_value = MagicMock()
        ControlledTimer.instances.clear()
        yield
        ControlledTimer.instances.clear()


@pytest.fixture(name="lpr")
def fixture_lpr(vis: MockViseron) -> ConcreteLPR:
    """Return a license plate recognition post processor."""
    MockComponent(vis, COMPONENT)
    MockCamera(vis, identifier=CAMERA_IDENTIFIER)
    config: dict[str, Any] = {
        CONFIG_CAMERAS: {CAMERA_IDENTIFIER: {CONFIG_MASK: [], CONFIG_LABELS: []}},
        CONFIG_KNOWN_PLATES: [PLATE],
        CONFIG_SAVE_PLATES: False,
        CONFIG_MIN_CONFIDENCE: 0.5,
        CONFIG_EXPIRE_AFTER: 60,
    }
    lpr = ConcreteLPR(vis, COMPONENT, config, CAMERA_IDENTIFIER)
    vis.dispatch_event.reset_mock()
    return lpr


def _plate_expired_count(vis: MockViseron) -> int:
    return sum(
        1
        for c in vis.dispatch_event.call_args_list
        if EVENT_PLATE_EXPIRED.format(camera_identifier=CAMERA_IDENTIFIER, plate=PLATE)
        == c.args[0]
    )


def test_stale_expiry_does_not_expire_newer_detection(
    lpr: ConcreteLPR, vis: MockViseron
) -> None:
    """A plate timer firing after a re-detection must not expire the new result."""
    with patch("viseron.domains.license_plate_recognition.Timer", ControlledTimer):
        frame = MagicMock(spec=PostProcessorFrame)
        frame.shared_frame = None

        # First detection: its plate timer fires and parks inside the callback.
        lpr.process(frame)
        first_plate_timer = ControlledTimer.instances[0]
        assert lpr._expire_plate == first_plate_timer._wrapped_function
        assert first_plate_timer.pre_gate.wait(timeout=5)

        # Second detection replaces the stored result and would cancel the
        # first timer - but its callback is already running.
        lpr.process(frame)

        # Let the stale callback finish: it must not expire the new result.
        first_plate_timer.release()
        assert PLATE in lpr._plates
        assert _plate_expired_count(vis) == 0

        # The second detection's timer expires the plate normally.
        second_plate_timer = ControlledTimer.instances[2]
        assert second_plate_timer.pre_gate.wait(timeout=5)
        second_plate_timer.release()
        assert PLATE not in lpr._plates
        assert _plate_expired_count(vis) == 1
