"""Tests for AbstractFaceRecognition and the LatestFaceImage entity."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from viseron.domains.camera.shared_frames import SharedFrame
from viseron.domains.face_recognition import AbstractFaceRecognition, EventFaceDetected
from viseron.domains.face_recognition.const import (
    CONFIG_EXPIRE_AFTER,
    CONFIG_SAVE_FACES,
    CONFIG_SAVE_UNKNOWN_FACES,
)
from viseron.domains.face_recognition.image import LatestFaceImage
from viseron.domains.post_processor.const import (
    CONFIG_CAMERAS,
    CONFIG_LABELS,
    CONFIG_MASK,
)

from tests.common import MockCamera, MockComponent

if TYPE_CHECKING:
    from collections.abc import Iterator

    from viseron.domains.post_processor import PostProcessorFrame

    from tests.conftest import MockViseron


CAMERA_IDENTIFIER = "test_camera"
COMPONENT = "test_face_recognition"
SNAPSHOT_PATH = "/snapshots/face_recognition/test.jpg"
COORDINATES = (0, 0, 10, 10)


class ConcreteFaceRecognition(AbstractFaceRecognition):
    """Concrete implementation for testing AbstractFaceRecognition."""

    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Return the frame unchanged."""
        return frame

    def face_recognition(
        self, post_processor_frame: PostProcessorFrame, detected_object
    ) -> None:
        """Not exercised directly in these tests."""


@pytest.fixture(autouse=True)
def patch_restartable_thread() -> Iterator[MagicMock]:
    """Patch RestartableThread so no live thread is spawned by the constructor."""
    with patch(
        "viseron.domains.post_processor.RestartableThread", autospec=True
    ) as mock_thread_cls:
        mock_thread_cls.return_value = MagicMock()
        yield mock_thread_cls


@pytest.fixture(name="mock_camera")
def fixture_mock_camera(vis: MockViseron) -> MockCamera:
    """Return a registered mock camera with mocked snapshots and frames."""
    camera = MockCamera(vis, identifier=CAMERA_IDENTIFIER)
    camera.save_snapshot.return_value = SNAPSHOT_PATH
    camera.shared_frames.get_decoded_frame_rgb.return_value = np.zeros(
        (10, 10, 3), dtype=np.uint8
    )
    return camera


@pytest.fixture(name="face_recognition_processor")
def fixture_face_recognition_processor(
    vis: MockViseron,
    mock_camera: MockCamera,  # noqa: ARG001  # pylint: disable=unused-argument
) -> ConcreteFaceRecognition:
    """Return a face recognition post processor with a registered camera."""
    MockComponent(vis, COMPONENT)
    config = {
        CONFIG_CAMERAS: {CAMERA_IDENTIFIER: {CONFIG_MASK: [], CONFIG_LABELS: []}},
        CONFIG_EXPIRE_AFTER: 9999,
        CONFIG_SAVE_FACES: True,
        CONFIG_SAVE_UNKNOWN_FACES: True,
    }
    # Entity generation lists the face folders on disk, which isn't relevant here.
    return ConcreteFaceRecognition(
        vis, COMPONENT, config, CAMERA_IDENTIFIER, generate_entities=False
    )


@pytest.fixture(name="mock_shared_frame")
def fixture_mock_shared_frame() -> SharedFrame:
    """Return a mock SharedFrame."""
    shared_frame = MagicMock(spec=SharedFrame)
    shared_frame.camera_identifier = CAMERA_IDENTIFIER
    return shared_frame


def _dispatched_face_events(vis: MockViseron) -> list[EventFaceDetected]:
    """Return the EventFaceDetected payloads dispatched so far.

    _save_face() also dispatches a DB-operation event via _insert_result(), on
    the same mocked dispatch_event, so this filters those out by type rather
    than assuming call order/count.
    """
    return [
        call.args[1]
        for call in vis.dispatch_event.call_args_list
        if isinstance(call.args[1], EventFaceDetected)
    ]


class TestAbstractFaceRecognitionLatestImage:
    """Test that face detected events only carry an image on first appearance."""

    def test_known_face_includes_image_only_on_first_appearance(
        self,
        face_recognition_processor: ConcreteFaceRecognition,
        vis: MockViseron,
        mock_shared_frame: SharedFrame,
    ) -> None:
        """Repeated detections of an already-tracked face shouldn't re-crop."""
        face_recognition_processor.known_face_found(
            "alice", COORDINATES, mock_shared_frame
        )
        face_recognition_processor.known_face_found(
            "alice", COORDINATES, mock_shared_frame
        )

        events = _dispatched_face_events(vis)
        assert len(events) == 2
        assert events[0].image is not None
        assert events[1].image is None

    def test_unknown_face_includes_image_only_on_first_appearance(
        self,
        face_recognition_processor: ConcreteFaceRecognition,
        vis: MockViseron,
        mock_shared_frame: SharedFrame,
    ) -> None:
        """Repeated unknown-face detections shouldn't re-crop either."""
        face_recognition_processor.unknown_face_found(COORDINATES, mock_shared_frame)
        face_recognition_processor.unknown_face_found(COORDINATES, mock_shared_frame)

        events = _dispatched_face_events(vis)
        assert len(events) == 2
        assert events[0].image is not None
        assert events[1].image is None

    def test_known_face_without_shared_frame_has_no_image(
        self,
        face_recognition_processor: ConcreteFaceRecognition,
        vis: MockViseron,
    ) -> None:
        """No shared frame means no image, even on first appearance."""
        face_recognition_processor.known_face_found("alice", COORDINATES, None)

        events = _dispatched_face_events(vis)
        assert len(events) == 1
        assert events[0].image is None


class TestLatestFaceImage:
    """Test the LatestFaceImage entity."""

    def test_handle_event_ignores_events_without_image(
        self, vis: MockViseron, mock_camera: MockCamera
    ) -> None:
        """The entity should be left untouched when there's no fresh image."""
        entity = LatestFaceImage(vis, mock_camera)
        event = MagicMock()
        event.data.image = None

        with patch.object(entity, "set_state") as mock_set_state:
            entity.handle_event(event)

        mock_set_state.assert_not_called()
        assert entity.image is None

    def test_handle_event_updates_image_when_present(
        self, vis: MockViseron, mock_camera: MockCamera
    ) -> None:
        """A fresh image should update the entity's image and attributes."""
        entity = LatestFaceImage(vis, mock_camera)
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        event = MagicMock()
        event.data.face.name = "alice"
        event.data.face.confidence = 0.93
        event.data.image = image

        with patch.object(entity, "set_state") as mock_set_state:
            entity.handle_event(event)

        mock_set_state.assert_called_once()
        assert entity.image is image
        assert entity.extra_attributes == {"face": "alice", "confidence": 0.93}
