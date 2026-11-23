"""CodeProjectAI face recognition tests."""

from unittest.mock import Mock, patch

import numpy as np
import pytest

from viseron import Viseron
from viseron.components.codeprojectai import CONFIG_SCHEMA
from viseron.components.codeprojectai.const import (
    COMPONENT,
    CONFIG_FACE_RECOGNITION,
    CONFIG_HOST,
    CONFIG_MIN_CONFIDENCE,
    CONFIG_PORT,
    CONFIG_TIMEOUT,
)
from viseron.components.codeprojectai.face_recognition import (
    FaceRecognition,
    setup as cpai_setup,
)
from viseron.domains.face_recognition.const import CONFIG_FACE_RECOGNITION_PATH

from tests.common import MockCamera, MockComponent
from tests.conftest import MockViseron

CAMERA_IDENTIFIER = "test_camera"


@pytest.fixture(name="config")
def fixture_config(tmp_path):
    """Fixture to provide a test configuration."""
    faces_dir = tmp_path / "faces"
    faces_dir.mkdir()
    (faces_dir / "alice").mkdir()
    return CONFIG_SCHEMA(
        {
            COMPONENT: {
                CONFIG_HOST: "localhost",
                CONFIG_PORT: 32168,
                CONFIG_TIMEOUT: 30,
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
        patch("viseron.components.codeprojectai.face_recognition.CodeProjectAIFace"),
        patch("viseron.domains.post_processor.RestartableThread"),
    ):
        recognizer = FaceRecognition(vis, config[COMPONENT], CAMERA_IDENTIFIER)
    recognizer._cpai = Mock()  # pylint: disable=protected-access
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
    """Test the setup function of the CodeProject.AI face recognizer."""
    with patch("viseron.components.codeprojectai.face_recognition.FaceRecognition"):
        assert cpai_setup(vis, config, CAMERA_IDENTIFIER) is True


def test_known_face_offsets_far_corner_by_crop_origin(
    face_recognition, post_processor_frame, detected_object
):
    """The detected face box is crop-local, so both corners are offset by the origin.

    A prediction of (10, 10, 50, 50) inside the crop at (960, 432) must map to
    (970, 442, 1010, 482), not to (970, 442, 1202, 590).
    """
    face_recognition._cpai.recognize.return_value = {  # pylint: disable=protected-access
        "success": True,
        "predictions": [
            {
                "userid": "alice",
                "confidence": 0.9,
                "x_min": 10,
                "y_min": 10,
                "x_max": 50,
                "y_max": 50,
            }
        ],
    }
    known_face_found = Mock()
    face_recognition.known_face_found = known_face_found

    face_recognition.face_recognition(post_processor_frame, detected_object)

    known_face_found.assert_called_once()
    assert known_face_found.call_args[0][1] == (970, 442, 1010, 482)
