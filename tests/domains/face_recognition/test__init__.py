"""Tests for AbstractFaceRecognition."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar
from threading import Event, Timer as RealTimer
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from viseron.domains.face_recognition import AbstractFaceRecognition
from viseron.domains.face_recognition.const import (
    CONFIG_EXPIRE_AFTER,
    CONFIG_FACE_RECOGNITION_PATH,
    CONFIG_SAVE_FACES,
    EVENT_FACE_EXPIRED,
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
COMPONENT = "test_face_recognition"
FACE = "alice"


class ControlledTimer(RealTimer):
    """Real timer with a short interval whose callback parks on a hold gate."""

    instances: ClassVar[list[ControlledTimer]] = []

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(0.05, *args[1:], **kwargs)
        self.daemon = True
        self.pre_gate = Event()
        self.hold = Event()
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


class ConcreteFaceRecognition(AbstractFaceRecognition):
    """Concrete implementation for testing."""

    domain = "face_recognition"
    snapshot_domain = SnapshotDomain.FACE_RECOGNITION

    def __post_init__(self, *args, **kwargs) -> None:
        """Post init hook."""

    def preprocess(self, frame: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
        """Return the frame unchanged."""
        return frame

    def face_recognition(
        self, post_processor_frame: PostProcessorFrame, detected_object: MagicMock
    ) -> None:
        """Recognize nothing."""


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


@pytest.fixture(name="face_recognition")
def fixture_face_recognition(
    vis: MockViseron, tmp_path: Any
) -> ConcreteFaceRecognition:
    """Return a face recognition post processor."""
    MockComponent(vis, COMPONENT)
    MockCamera(vis, identifier=CAMERA_IDENTIFIER)
    config: dict[str, Any] = {
        CONFIG_CAMERAS: {CAMERA_IDENTIFIER: {CONFIG_MASK: [], CONFIG_LABELS: []}},
        CONFIG_EXPIRE_AFTER: 60,
        CONFIG_FACE_RECOGNITION_PATH: str(tmp_path),
        CONFIG_SAVE_FACES: False,
    }
    recognizer = ConcreteFaceRecognition(
        vis, COMPONENT, config, CAMERA_IDENTIFIER, generate_entities=False
    )
    vis.dispatch_event.reset_mock()
    return recognizer


def _face_expired_count(vis: MockViseron) -> int:
    return sum(
        1
        for c in vis.dispatch_event.call_args_list
        if EVENT_FACE_EXPIRED.format(camera_identifier=CAMERA_IDENTIFIER, face=FACE)
        == c.args[0]
    )


def test_stale_expiry_does_not_expire_newer_detection(
    face_recognition: ConcreteFaceRecognition, vis: MockViseron
) -> None:
    """A face timer firing after a re-detection must not expire the new entry."""
    with patch("viseron.domains.face_recognition.Timer", ControlledTimer):
        coordinates = (0, 0, 10, 10)

        # First detection: its expiry timer fires and parks inside the callback.
        face_recognition.known_face_found(FACE, coordinates, None)
        first_timer = ControlledTimer.instances[0]
        assert face_recognition.expire_face == first_timer._wrapped_function
        assert first_timer.pre_gate.wait(timeout=5)

        # Second detection replaces the stored entry and would cancel the
        # first timer - but its callback is already running.
        face_recognition.known_face_found(FACE, coordinates, None)

        # Let the stale callback finish: it must not expire the new entry.
        first_timer.release()
        assert FACE in face_recognition._faces
        assert _face_expired_count(vis) == 0

        # The second detection's timer expires the face normally.
        second_timer = ControlledTimer.instances[1]
        assert second_timer.pre_gate.wait(timeout=5)
        second_timer.release()
        assert FACE not in face_recognition._faces
        assert _face_expired_count(vis) == 1
