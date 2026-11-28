"""DeepStack face recognition tests."""

from unittest.mock import Mock, patch

import deepstack.core as ds
import numpy as np
import pytest

from viseron import Viseron
from viseron.components.deepstack import CONFIG_SCHEMA
from viseron.components.deepstack.const import (
    COMPONENT,
    CONFIG_FACE_RECOGNITION,
    CONFIG_HOST,
    CONFIG_MIN_CONFIDENCE,
    CONFIG_PORT,
)
from viseron.components.deepstack.face_recognition import FaceRecognition, setup
from viseron.domains.face_recognition.const import CONFIG_FACE_RECOGNITION_PATH

from tests.common import MockCamera, MockComponent
from tests.conftest import MockViseron

CAMERA_IDENTIFIER = "test_camera"


@pytest.fixture
def config(tmp_path):
    """Fixture to provide a test configuration."""
    faces_dir = tmp_path / "faces"
    faces_dir.mkdir()
    (faces_dir / "alice").mkdir()
    return CONFIG_SCHEMA(
        {
            COMPONENT: {
                CONFIG_HOST: "localhost",
                CONFIG_PORT: 8080,
                CONFIG_FACE_RECOGNITION: {
                    CONFIG_FACE_RECOGNITION_PATH: str(faces_dir),
                    CONFIG_MIN_CONFIDENCE: 0.5,
                    "cameras": {CAMERA_IDENTIFIER: {}},
                },
            }
        }
    )


@pytest.fixture
def face_recognition(vis: MockViseron, config):
    """Fixture to provide a FaceRecognition instance with a mocked client."""
    _ = MockComponent(vis, COMPONENT)
    _ = MockCamera(vis, identifier=CAMERA_IDENTIFIER)
    with (
        patch("viseron.components.deepstack.face_recognition.DeepstackFace"),
        patch("viseron.domains.post_processor.RestartableThread"),
    ):
        recognizer = FaceRecognition(vis, config[COMPONENT], CAMERA_IDENTIFIER)
    recognizer._ds = Mock()  # pylint: disable=protected-access
    return recognizer


@pytest.fixture
def post_processor_frame():
    """Fixture to provide a mocked PostProcessorFrame."""
    return Mock(
        frame=np.zeros((1080, 1920, 3), dtype=np.uint8),
        shared_frame=Mock(),
    )


@pytest.fixture
def detected_object():
    """Fixture to provide a mocked DetectedObject.

    Relative (0.5, 0.4, 0.6, 0.5) on a 1920x1080 frame resolves to the absolute
    crop (960, 432, 1152, 540).
    """
    return Mock(rel_x1=0.5, rel_y1=0.4, rel_x2=0.6, rel_y2=0.5)


def test_setup(vis: Viseron, config):
    """Test the setup function of the DeepStack face recognizer."""
    with patch("viseron.components.deepstack.face_recognition.FaceRecognition"):
        assert setup(vis, config, CAMERA_IDENTIFIER) is True


def test_face_recognition_returns_after_deepstack_error(
    face_recognition, post_processor_frame, detected_object
):
    """A DeepstackException must not crash the recognizer with an UnboundLocalError."""
    face_recognition._ds.recognize.side_effect = ds.DeepstackException(
        "connection refused"  # pylint: disable=protected-access
    )

    # Must log the error and return instead of raising UnboundLocalError
    face_recognition.face_recognition(post_processor_frame, detected_object)
