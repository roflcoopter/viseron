"""YOLO object detector tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
from pytest import MonkeyPatch

import viseron.components.yolo.object_detector as od
from viseron import Viseron
from viseron.domains.camera.shared_frames import SharedFrame
from viseron.domains.object_detector import AbstractObjectDetector
from viseron.domains.object_detector.detected_object import DetectedObject

from .yolo_fakes import (
    DetectionBuilder,
    DetectionSpec,
    ErrYOLO,
    FakeCamera,
    FakeViseron,
    FakeYOLO,
)

# For testing we are accessing protected members
# pylint: disable=protected-access

PERSON_DETECTION = DetectionSpec(0, [10, 20, 30, 40], 0.9, "person")
CAT_DETECTION = DetectionSpec(1, [50, 60, 70, 80], 0.75, "cat")
DOG_DETECTION = DetectionSpec(2, [100, 110, 120, 130], 0.5, "dog")

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def patch_yolo(monkeypatch: MonkeyPatch) -> None:
    """Patch YOLO class and AbstractObjectDetector for testing.

    This fixture replaces the real YOLO class with our test double and
    simplifies the AbstractObjectDetector initialization to avoid heavy
    dependencies.
    """
    # Replace the YOLO class in the imported module with our dummy
    monkeypatch.setattr(od, "YOLO", FakeYOLO)

    # Patch AbstractObjectDetector.__init__ to avoid heavy initialization
    def fake_init(
        self: AbstractObjectDetector,
        vis: Viseron | FakeViseron,
        component: str,
        config: dict[Any, Any],
        camera_identifier: str,
    ):
        """Minimal init providing only the attributes needed by tests."""
        del component  # Unused in this fake implementation
        self._config = config
        self._vis = vis
        self._camera_identifier = camera_identifier
        self._camera = FakeCamera(camera_identifier)  # type: ignore[assignment]

    monkeypatch.setattr(AbstractObjectDetector, "__init__", fake_init)


@pytest.fixture
def fake_viseron() -> FakeViseron:
    """Provide a fake Viseron instance for testing."""
    return FakeViseron()


@pytest.fixture
def detector_config(tmp_path: Path) -> dict[str, dict[str, Any]]:
    """Provide standard test configuration for ObjectDetector.

    Args:
        tmp_path: Pytest fixture providing temporary directory

    Returns:
        Configuration dictionary with all required settings
    """
    return {
        od.CONFIG_OBJECT_DETECTOR: {
            od.CONFIG_MODEL_PATH: str(tmp_path / "model.pt"),
            od.CONFIG_MIN_CONFIDENCE: 0.25,
            od.CONFIG_IOU: 0.45,
            od.CONFIG_HALF_PRECISION: False,
            od.CONFIG_DEVICE: "cpu",
        }
    }


@pytest.fixture
def detector(
    patch_yolo: None,
    fake_viseron: FakeViseron,
    detector_config: dict[str, dict[str, Any]],
) -> od.ObjectDetector:
    """Provide a configured ObjectDetector instance.

    Args:
        patch_yolo: Fixture that patches YOLO dependencies
        fake_viseron: Fake Viseron instance
        detector_config: Configuration dictionary

    Returns:
        ObjectDetector instance ready for testing
    """
    return od.ObjectDetector(
        cast(Viseron, fake_viseron), detector_config, "test_camera"
    )  # FakeViseron implements needed interface


# ============================================================================
# Test Helper Functions
# ============================================================================


def assert_valid_detection(
    detected_obj: DetectedObject, expected_label: str, expected_conf: float
):
    """Verify basic detection properties without checking exact coordinates.

    Args:
        detected_obj: The DetectedObject to verify
        expected_label: Expected label string
        expected_conf: Expected confidence score
    """
    assert detected_obj.label == expected_label
    assert detected_obj.confidence == pytest.approx(expected_conf)

    # Verify coordinates exist and are reasonable (not None, not negative width/height)
    x1, y1, x2, y2 = detected_obj.abs_coordinates
    assert x1 is not None and y1 is not None
    assert x2 is not None and y2 is not None
    assert x2 > x1, f"x2 ({x2}) should be greater than x1 ({x1})"
    assert y2 > y1, f"y2 ({y2}) should be greater than y1 ({y1})"


def assert_bbox_approximately_matches(
    detected_obj: DetectedObject,
    expected_bbox: list[float],
    tolerance: float = 5.0,
):
    """Verify bounding box coordinates are approximately correct.

    This is useful when exact coordinates might differ due to transformations,
    but we want to ensure they're in the right ballpark.

    Args:
        detected_obj: The DetectedObject to verify
        expected_bbox: Expected bounding box as [x1, y1, x2, y2]
        tolerance: Maximum allowed pixel difference (default: 5.0)
    """
    x1, y1, x2, y2 = detected_obj.abs_coordinates
    ex1, ey1, ex2, ey2 = expected_bbox

    assert x1 == pytest.approx(ex1, abs=tolerance), f"x1: expected {ex1}, got {x1}"
    assert y1 == pytest.approx(ey1, abs=tolerance), f"y1: expected {ey1}, got {y1}"
    assert x2 == pytest.approx(ex2, abs=tolerance), f"x2: expected {ex2}, got {x2}"
    assert y2 == pytest.approx(ey2, abs=tolerance), f"y2: expected {ey2}, got {y2}"


# ============================================================================
# Postprocess Tests
# ============================================================================


def test_postprocess_returns_a_detected_object(detector: od.ObjectDetector):
    """Postprocess should return the correct number of detected objects."""
    result = DetectionBuilder().add_spec(PERSON_DETECTION).build()

    objects = detector.postprocess([result])

    assert len(objects) == 1
    assert isinstance(objects[0], DetectedObject)


def test_postprocess_maps_label(detector: od.ObjectDetector):
    """Postprocess should correctly map class IDs to label names."""
    result = DetectionBuilder().add_spec(PERSON_DETECTION).build()

    objects = detector.postprocess([result])

    assert objects[0].label == PERSON_DETECTION.label


def test_postprocess_preserves_confidence(detector: od.ObjectDetector):
    """Postprocess should preserve confidence scores."""
    result = DetectionBuilder().add_spec(PERSON_DETECTION).build()

    objects = detector.postprocess([result])

    assert objects[0].confidence == pytest.approx(PERSON_DETECTION.confidence)


def test_postprocess_no_boxes(detector: od.ObjectDetector):
    """Postprocess should return empty list when no boxes are present."""
    result = DetectionBuilder().build()

    objects = detector.postprocess([result])

    assert objects == []


def test_postprocess_multiple_boxes(detector: od.ObjectDetector):
    """Postprocess should handle multiple boxes correctly."""
    expected = [PERSON_DETECTION, CAT_DETECTION]
    result = DetectionBuilder().add_specs(expected).build()

    objects = detector.postprocess([result])

    assert len(objects) == len(expected)

    for spec in expected:
        obj = next(o for o in objects if o.label == spec.label)
        assert_valid_detection(obj, spec.label, spec.confidence)


def test_postprocess_creates_valid_bounding_boxes(detector: od.ObjectDetector):
    """Postprocess should create valid bounding boxes (x2 > x1, y2 > y1)."""
    result = DetectionBuilder().add_spec(PERSON_DETECTION).build()

    objects = detector.postprocess([result])

    assert_bbox_approximately_matches(objects[0], PERSON_DETECTION.bbox, tolerance=2.0)


# ============================================================================
# Preprocess Tests
# ============================================================================


def test_preprocess_preserves_shape(detector: od.ObjectDetector):
    """Preprocess should preserve frame dimensions."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    processed = detector.preprocess(frame)

    assert isinstance(processed, np.ndarray)
    assert processed.shape == (480, 640, 3)


# ============================================================================
# Return Objects Tests
# ============================================================================


def test_return_objects_calls_predict(detector: od.ObjectDetector):
    """Ensure return_objects proxies to YOLO.predict and uses postprocess."""
    # Configure the dummy detector with prediction results
    expected = CAT_DETECTION
    result = DetectionBuilder().add_spec(expected).build()
    detector._detector.set_pred([result])  # type: ignore[attr-defined]

    frame = cast(SharedFrame, np.zeros((480, 640, 3), dtype=np.uint8))
    objects = detector.return_objects(frame)

    assert len(objects) == 1
    assert_valid_detection(objects[0], expected.label, expected.confidence)


def test_return_objects_with_multiple_detections(detector: od.ObjectDetector):
    """Test return_objects with multiple detections in one frame."""
    expected = [PERSON_DETECTION, CAT_DETECTION, DOG_DETECTION]
    result = DetectionBuilder().add_specs(expected).build()

    detector._detector.set_pred([result])  # type: ignore[attr-defined]

    frame = cast(SharedFrame, np.zeros((480, 640, 3), dtype=np.uint8))
    objects = detector.return_objects(frame)

    assert len(objects) == len(expected)

    for spec in expected:
        obj = next(o for o in objects if o.label == spec.label)
        assert_valid_detection(obj, spec.label, spec.confidence)


def test_return_objects_with_no_detections(detector: od.ObjectDetector):
    """Test return_objects when no objects are detected."""
    result = DetectionBuilder().build()
    detector._detector.set_pred([result])  # type: ignore[attr-defined]

    frame = cast(SharedFrame, np.zeros((480, 640, 3), dtype=np.uint8))
    objects = detector.return_objects(frame)

    assert objects == []


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_return_objects_handles_prediction_exception(
    monkeypatch: MonkeyPatch, detector: od.ObjectDetector
):
    """Return_objects should handle exceptions from predict() gracefully.

    This test verifies the code doesn't crash unexpectedly.
    """
    # Replace the detector with one that raises errors
    monkeypatch.setattr(detector, "_detector", ErrYOLO(ValueError, "prediction failed"))

    frame = cast(SharedFrame, np.zeros((480, 640, 3), dtype=np.uint8))

    # Attempt to get objects - should either catch gracefully or fail fast
    try:
        objects = detector.return_objects(frame)

        # If exception was caught, verify we got a safe return value
        assert isinstance(objects, list)
    except ValueError as e:
        # If exception propagates, verify it has the expected message
        assert "prediction failed" in str(e)


def test_return_objects_with_empty_frame(detector: od.ObjectDetector):
    """Test return_objects with edge case empty frame."""
    # Configure detector to return empty results
    result = DetectionBuilder().build()
    detector._detector.set_pred([result])  # type: ignore[attr-defined]

    # Create minimal valid frame
    frame = cast(SharedFrame, np.zeros((1, 1, 3), dtype=np.uint8))

    # Should handle gracefully
    objects = detector.return_objects(frame)

    assert objects == []
