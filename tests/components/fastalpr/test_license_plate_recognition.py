"""fast-alpr license plate recognition tests."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from viseron import Viseron
from viseron.components.fastalpr import CONFIG_SCHEMA
from viseron.components.fastalpr.const import COMPONENT, INSTANCES, LOCK
from viseron.components.fastalpr.license_plate_recognition import (
    LicensePlateRecognition,
    setup as fastalpr_setup,
)
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.exceptions import DomainNotReady

from tests.common import MockCamera

CAMERA_IDENTIFIER = "test_camera"


@pytest.fixture
def config():
    """Fixture to provide a test configuration."""
    return CONFIG_SCHEMA(
        {
            "fastalpr": {
                "license_plate_recognition": {
                    "cameras": {
                        CAMERA_IDENTIFIER: {},
                    },
                },
            }
        }
    )["fastalpr"]


@pytest.fixture
def mock_alpr():
    """Fixture that patches the fast_alpr.ALPR class."""
    with patch("viseron.components.fastalpr.license_plate_recognition.ALPR") as mock:
        yield mock


def make_instance(vis: Viseron, config, camera) -> LicensePlateRecognition:
    """Build a LicensePlateRecognition instance.

    Bypasses the heavy AbstractPostProcessor.__init__ (real threads/event
    listeners), instead only exercising the fastalpr-specific logic under test.
    """
    with patch.object(
        LicensePlateRecognition, "__init__", MagicMock(return_value=None)
    ):
        instance = LicensePlateRecognition.__new__(LicensePlateRecognition)
    instance._vis = vis
    instance._config = config["license_plate_recognition"]
    instance._camera = camera
    instance._alpr = instance._get_alpr(vis, instance._config)
    return instance


@pytest.mark.usefixtures("mock_alpr")
def test_setup(vis: Viseron, config):
    """Test the setup function instantiates LicensePlateRecognition."""
    vis.data[COMPONENT] = {LOCK: threading.Lock(), INSTANCES: {}}
    with patch(
        "viseron.components.fastalpr.license_plate_recognition.LicensePlateRecognition"
    ) as mock_lpr:
        result = fastalpr_setup(vis, config, CAMERA_IDENTIFIER)
        assert result is True
        mock_lpr.assert_called_once_with(vis, config, CAMERA_IDENTIFIER)


def test_get_alpr_caches_identical_config(vis: Viseron, config, mock_alpr):
    """Two cameras with identical model config should share one ALPR instance."""
    vis.data[COMPONENT] = {LOCK: threading.Lock(), INSTANCES: {}}
    camera = MockCamera(vis, identifier=CAMERA_IDENTIFIER)
    instance_1 = make_instance(vis, config, camera)
    instance_2 = make_instance(vis, config, camera)

    mock_alpr.assert_called_once()
    assert instance_1._alpr is instance_2._alpr


def test_get_alpr_raises_domain_not_ready(vis: Viseron, config, mock_alpr):
    """A failure loading the models should raise DomainNotReady."""
    vis.data[COMPONENT] = {LOCK: threading.Lock(), INSTANCES: {}}
    mock_alpr.side_effect = OSError("failed to download model")
    camera = MockCamera(vis, identifier=CAMERA_IDENTIFIER)

    with pytest.raises(DomainNotReady):
        make_instance(vis, config, camera)


@pytest.mark.usefixtures("mock_alpr")
def test_preprocess_converts_rgb_to_bgr(vis: Viseron, config):
    """preprocess() should convert the incoming RGB frame to BGR."""
    vis.data[COMPONENT] = {LOCK: threading.Lock(), INSTANCES: {}}
    camera = MockCamera(vis, identifier=CAMERA_IDENTIFIER)
    instance = make_instance(vis, config, camera)

    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    frame[0, 0] = [1, 2, 3]  # R, G, B
    processed = instance.preprocess(frame)

    assert list(processed[0, 0]) == [3, 2, 1]  # B, G, R


def _make_alpr_result(text, confidence, x1, y1, x2, y2):
    """Build a fake fast_alpr ALPRResult-like object."""
    ocr = MagicMock(text=text, confidence=confidence)
    bbox = MagicMock(x1=x1, y1=y1, x2=x2, y2=y2)
    detection = MagicMock(bounding_box=bbox)
    return MagicMock(ocr=ocr, detection=detection)


@pytest.mark.usefixtures("mock_alpr")
def test_process_frame_coordinates_and_text(vis: Viseron, config):
    """Detected plate coordinates should be offset by the crop origin."""
    vis.data[COMPONENT] = {LOCK: threading.Lock(), INSTANCES: {}}
    camera = MockCamera(vis, identifier=CAMERA_IDENTIFIER, resolution=(1000, 1000))
    instance = make_instance(vis, config, camera)
    instance._alpr.predict.return_value = [
        _make_alpr_result("ABC123", 0.9, 10, 20, 30, 40)
    ]

    detected_object = DetectedObject(
        "car", 0.9, 0.1, 0.1, 0.3, 0.3, frame_res=(1000, 1000)
    )
    frame = np.zeros((1000, 1000, 3), dtype=np.uint8)

    detections = instance._process_frame(frame, detected_object)

    assert len(detections) == 1
    plate = detections[0]
    assert plate.plate == "ABC123"
    assert plate.confidence == 0.9
    # crop origin is (100, 100), so detection (10,20,30,40) -> (110,120,130,140)
    assert plate.rel_x1 == pytest.approx(0.11, abs=0.001)
    assert plate.rel_y1 == pytest.approx(0.12, abs=0.001)
    assert plate.rel_x2 == pytest.approx(0.13, abs=0.001)
    assert plate.rel_y2 == pytest.approx(0.14, abs=0.001)


@pytest.mark.usefixtures("mock_alpr")
def test_process_frame_drops_none_ocr(vis: Viseron, config):
    """A detection with no OCR result should be dropped."""
    vis.data[COMPONENT] = {LOCK: threading.Lock(), INSTANCES: {}}
    camera = MockCamera(vis, identifier=CAMERA_IDENTIFIER, resolution=(1000, 1000))
    instance = make_instance(vis, config, camera)
    bbox = MagicMock(x1=10, y1=20, x2=30, y2=40)
    detection = MagicMock(bounding_box=bbox)
    instance._alpr.predict.return_value = [MagicMock(ocr=None, detection=detection)]

    detected_object = DetectedObject(
        "car", 0.9, 0.1, 0.1, 0.3, 0.3, frame_res=(1000, 1000)
    )
    frame = np.zeros((1000, 1000, 3), dtype=np.uint8)

    detections = instance._process_frame(frame, detected_object)

    assert not detections


@pytest.mark.usefixtures("mock_alpr")
def test_process_frame_discards_unrecognized_plates_by_default(vis: Viseron, config):
    """An empty-text OCR result should be dropped when the config default applies."""
    vis.data[COMPONENT] = {LOCK: threading.Lock(), INSTANCES: {}}
    camera = MockCamera(vis, identifier=CAMERA_IDENTIFIER, resolution=(1000, 1000))
    instance = make_instance(vis, config, camera)
    instance._alpr.predict.return_value = [_make_alpr_result("", 0.99, 10, 20, 30, 40)]

    detected_object = DetectedObject(
        "car", 0.9, 0.1, 0.1, 0.3, 0.3, frame_res=(1000, 1000)
    )
    frame = np.zeros((1000, 1000, 3), dtype=np.uint8)

    detections = instance._process_frame(frame, detected_object)

    assert not detections


@pytest.mark.usefixtures("mock_alpr")
def test_process_frame_keeps_unrecognized_plates_when_disabled(vis: Viseron, config):
    """An empty-text OCR result should be kept when the filter is disabled."""
    vis.data[COMPONENT] = {LOCK: threading.Lock(), INSTANCES: {}}
    camera = MockCamera(vis, identifier=CAMERA_IDENTIFIER, resolution=(1000, 1000))
    config["license_plate_recognition"]["discard_unrecognized_plates"] = False
    instance = make_instance(vis, config, camera)
    instance._alpr.predict.return_value = [_make_alpr_result("", 0.99, 10, 20, 30, 40)]

    detected_object = DetectedObject(
        "car", 0.9, 0.1, 0.1, 0.3, 0.3, frame_res=(1000, 1000)
    )
    frame = np.zeros((1000, 1000, 3), dtype=np.uint8)

    detections = instance._process_frame(frame, detected_object)

    assert len(detections) == 1
    assert detections[0].plate == ""


@pytest.mark.usefixtures("mock_alpr")
def test_process_frame_filters_low_confidence(vis: Viseron, config):
    """Results below the configured min_confidence should be dropped."""
    vis.data[COMPONENT] = {LOCK: threading.Lock(), INSTANCES: {}}
    camera = MockCamera(vis, identifier=CAMERA_IDENTIFIER, resolution=(1000, 1000))
    config["license_plate_recognition"]["min_confidence"] = 0.8
    instance = make_instance(vis, config, camera)
    instance._alpr.predict.return_value = [
        _make_alpr_result("ABC123", 0.5, 10, 20, 30, 40),
        _make_alpr_result("XYZ789", [0.9, 0.9, 0.9, 0.9, 0.9, 0.9], 10, 20, 30, 40),
    ]

    detected_object = DetectedObject(
        "car", 0.9, 0.1, 0.1, 0.3, 0.3, frame_res=(1000, 1000)
    )
    frame = np.zeros((1000, 1000, 3), dtype=np.uint8)

    detections = instance._process_frame(frame, detected_object)

    assert len(detections) == 1
    assert detections[0].plate == "XYZ789"
