"""CodeProjectAI object detector tests."""
from unittest.mock import Mock, patch

import numpy as np
import pytest

from viseron import Viseron
from viseron.components.codeprojectai import CONFIG_SCHEMA
from viseron.components.codeprojectai.const import COMPONENT
from viseron.components.codeprojectai.object_detector import (
    ObjectDetector,
    setup as cpai_setup,
)
from viseron.domains.object_detector.const import DOMAIN as OBJECT_DETECTOR_DOMAIN
from viseron.domains.object_detector.detected_object import DetectedObject

from tests.common import MockCamera, MockComponent
from tests.conftest import MockViseron

CAMERA_IDENTIFIER = "test_camera"


@pytest.fixture(name="mock_detected_object")
def fixture_mock_detected_object():
    """Fixture to provide a mocked DetectedObject class."""
    with patch(
        "viseron.components.codeprojectai.object_detector.DetectedObject"
    ) as mock:
        yield mock


@pytest.fixture
def config():
    """
    Fixture to provide a test configuration.

    Returns:
        dict: A dictionary containing the test configuration.
    """
    return CONFIG_SCHEMA(
        {
            "codeprojectai": {
                "host": "localhost",
                "port": 32168,
                "object_detector": {
                    "image_size": 640,
                    "cameras": {
                        CAMERA_IDENTIFIER: {
                            "labels": [
                                {
                                    "label": "person",
                                    "confidence": 0.8,
                                    "trigger_event_recording": True,
                                }
                            ],
                        }
                    },
                },
            }
        }
    )


def test_setup(vis: Viseron, config):
    """
    Test the setup function of the CodeProjectAI object detector.

    Args:
        vis (Viseron): The Viseron instance.
        config (dict): The configuration dictionary.
    """
    with patch(
        "viseron.components.codeprojectai.object_detector.ObjectDetector"
    ) as mock_object_detector:
        result = cpai_setup(vis, config, CAMERA_IDENTIFIER)
        assert result is True
        mock_object_detector.assert_called_once_with(vis, config, CAMERA_IDENTIFIER)


def test_object_detector_init(vis: MockViseron, config):
    """
    Test the initialization of the ObjectDetector class.

    Args:
        vis (MockViseron): The mocked Viseron instance.
        config (dict): The configuration dictionary.
    """
    _ = MockComponent(COMPONENT, vis)
    _ = MockCamera(vis, identifier=CAMERA_IDENTIFIER)
    with patch("viseron.components.codeprojectai.object_detector.CodeProjectAIObject"):
        detector = ObjectDetector(vis, config["codeprojectai"], CAMERA_IDENTIFIER)
        assert detector._image_resolution == (  # pylint: disable=protected-access
            640,
            640,
        )
        vis.mocked_register_domain.assert_called_with(
            OBJECT_DETECTOR_DOMAIN, CAMERA_IDENTIFIER, detector
        )


def test_preprocess(vis: Viseron, config):
    """
    Test the preprocess method of the ObjectDetector class.

    Args:
        vis (Viseron): The Viseron instance.
        config (dict): The configuration dictionary.
    """
    _ = MockComponent(COMPONENT, vis)
    _ = MockCamera(vis, identifier=CAMERA_IDENTIFIER)
    with patch("viseron.components.codeprojectai.object_detector.CodeProjectAIObject"):
        detector = ObjectDetector(vis, config["codeprojectai"], CAMERA_IDENTIFIER)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        processed = detector.preprocess(frame)
        assert isinstance(processed, bytes)


def test_postprocess(vis: Viseron, config):
    """
    Test the postprocess method of the ObjectDetector class.

    Args:
        vis (Viseron): The Viseron instance.
        config (dict): The configuration dictionary.
    """
    _ = MockComponent(COMPONENT, vis)
    _ = MockCamera(vis, identifier=CAMERA_IDENTIFIER)
    with patch("viseron.components.codeprojectai.object_detector.CodeProjectAIObject"):
        detector = ObjectDetector(vis, config["codeprojectai"], CAMERA_IDENTIFIER)
        detections = [
            {
                "label": "person",
                "confidence": 0.9,
                "x_min": 100,
                "y_min": 100,
                "x_max": 200,
                "y_max": 200,
            }
        ]
        objects = detector.postprocess(detections)
        assert len(objects) == 1
        assert isinstance(objects[0], DetectedObject)


@patch("viseron.components.codeprojectai.object_detector.CodeProjectAIObject.detect")
def test_return_objects_success(mock_detect, vis: Viseron, config):
    """
    Test the return_objects method of the ObjectDetector class for successful detection.

    Args:
        mock_detect (MagicMock): Mocked detect method.
        vis (Viseron): The Viseron instance.
        config (dict): The configuration dictionary.
    """
    _ = MockComponent(COMPONENT, vis)
    _ = MockCamera(vis, identifier=CAMERA_IDENTIFIER)
    mock_detect.return_value = [
        {
            "label": "person",
            "confidence": 0.9,
            "x_min": 100,
            "y_min": 100,
            "x_max": 200,
            "y_max": 200,
        }
    ]
    detector = ObjectDetector(vis, config["codeprojectai"], CAMERA_IDENTIFIER)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    objects = detector.return_objects(frame)
    assert len(objects) == 1
    assert isinstance(objects[0], DetectedObject)


@patch("codeprojectai.core.CodeProjectAIObject.detect")
def test_return_objects_exception(mock_detect, vis: Viseron, config):
    """
    Test the return_objects method of the ObjectDetector class when an exception occurs.

    Args:
        mock_detect (MagicMock): Mocked detect method.
        vis (Viseron): The Viseron instance.
        config (dict): The configuration dictionary.
    """
    from codeprojectai.core import (  # pylint: disable=import-outside-toplevel
        CodeProjectAIException,
    )

    _ = MockComponent(COMPONENT, vis)
    _ = MockCamera(vis, identifier=CAMERA_IDENTIFIER)
    mock_detect.side_effect = CodeProjectAIException("Test error")
    detector = ObjectDetector(vis, config["codeprojectai"], CAMERA_IDENTIFIER)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    objects = detector.return_objects(frame)
    assert len(objects) == 0


def test_object_detector_init_no_image_size(vis: Viseron, config, mock_detected_object):
    """
    Test the initialization of the ObjectDetector class when image_size is not set.

    Args:
        vis (Viseron): The Viseron instance.
        config (dict): The configuration dictionary.
        mock_detected_object (MagicMock): Mocked DetectedObject class.
    """
    with patch("viseron.components.codeprojectai.object_detector.CodeProjectAIObject"):
        # Set non-square image resolution
        config["codeprojectai"]["object_detector"]["image_size"] = None

        # Mock camera with non-square resolution
        _ = MockComponent(COMPONENT, vis)
        _ = MockCamera(vis, identifier=CAMERA_IDENTIFIER, resolution=(1280, 720))

        detector = ObjectDetector(vis, config["codeprojectai"], CAMERA_IDENTIFIER)

        detections = [
            {
                "label": "person",
                "confidence": 0.9,
                "x_min": 100,
                "y_min": 100,
                "x_max": 200,
                "y_max": 200,
            }
        ]

        objects = detector.postprocess(detections)

        assert len(objects) == 1
        assert isinstance(objects[0], Mock)

        # Check if from_absolute was called instead of from_absolute_letterboxed
        mock_detected_object.from_absolute.assert_called_once()
        mock_detected_object.from_absolute_letterboxed.assert_not_called()

        # Check the arguments passed to from_absolute
        mock_detected_object.from_absolute.assert_called_with(
            "person",
            0.9,
            100,
            100,
            200,
            200,
            frame_res=(1280, 720),
            model_res=(1280, 720),
        )


def test_postprocess_square_resolution(vis: Viseron, config, mock_detected_object):
    """
    Test the postprocess method of the ObjectDetector class with a square resolution.

    Args:
        vis (Viseron): The Viseron instance.
        config (dict): The configuration dictionary.
        mock_detected_object (MagicMock): Mocked DetectedObject class.
    """
    with patch("viseron.components.codeprojectai.object_detector.CodeProjectAIObject"):
        # Set square image resolution
        config["codeprojectai"]["object_detector"]["image_size"] = 640

        # Mock camera with square resolution
        _ = MockComponent(COMPONENT, vis)
        _ = MockCamera(vis, identifier=CAMERA_IDENTIFIER, resolution=(640, 640))

        detector = ObjectDetector(vis, config["codeprojectai"], CAMERA_IDENTIFIER)

        detections = [
            {
                "label": "person",
                "confidence": 0.9,
                "x_min": 100,
                "y_min": 100,
                "x_max": 200,
                "y_max": 200,
            }
        ]

        objects = detector.postprocess(detections)

        assert len(objects) == 1

        # Check if from_absolute_letterboxed was called instead of from_absolute
        mock_detected_object.from_absolute_letterboxed.assert_called_once()
        mock_detected_object.from_absolute.assert_not_called()

        mock_detected_object.from_absolute_letterboxed.assert_called_with(
            "person",
            0.9,
            100,
            100,
            200,
            200,
            frame_res=(640, 640),
            model_res=(640, 640),
        )
