"""Fake implementations for YOLO testing.

This module provides test doubles that mimic the ultralytics YOLO library
interfaces without requiring the actual library or model files.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


class Box:
    """Represents a single detected bounding box.

    Mimics the ultralytics Box object with the minimal interface needed
    for testing: cls (class ID), xyxy (coordinates), and conf (confidence).
    """

    def __init__(self, cls_val: int, xy_val: list[float], conf_val: float):
        """Initialize a box with detection data.

        Args:
            cls_val: Class ID as an integer
            xy_val: Bounding box coordinates as [x1, y1, x2, y2]
            conf_val: Confidence score as a float
        """
        self.cls = np.array([cls_val])
        self.xyxy = np.array([xy_val])
        self.conf = conf_val


class FakeBoxes:
    """Iterator for bounding box collections.

    Mimics the ultralytics Boxes collection that can be iterated to yield
    individual Box objects.
    """

    def __init__(
        self,
        cls_vals: list[int],
        xyxy_vals: list[list[float]],
        conf_vals: list[float],
    ):
        """Store detection data for iteration.

        Args:
            cls_vals: List of class IDs
            xyxy_vals: List of bounding boxes as [x1, y1, x2, y2]
            conf_vals: List of confidence scores
        """
        self._cls = list(cls_vals)
        self._xyxy = list(xyxy_vals)
        self._conf = list(conf_vals)

    def __iter__(self):
        """Yield Box objects compatible with ObjectDetector.postprocess.

        Yields:
            Box: Individual box objects with cls, xyxy, and conf attributes
        """
        for c, xy, conf in zip(self._cls, self._xyxy, self._conf):
            yield Box(c, xy, conf)


class FakeResult:
    """Test double for ultralytics Results object.

    Implements the minimal interface required by ObjectDetector:
    - names: Dict mapping class IDs to label strings
    - boxes: Iterable of Box objects
    - orig_shape: Original image shape as (height, width)
    """

    def __init__(
        self,
        names: dict[int, str],
        boxes: Any,
        orig_shape: tuple[int, int] = (480, 640),
    ):
        """Create a detection result.

        Args:
            names: Dictionary mapping class IDs to label names
            boxes: FakeBoxes or list of Box objects
            orig_shape: Original image dimensions (height, width)
        """
        self.names = names
        self.boxes = boxes
        self.orig_shape = orig_shape


class FakeYOLO:
    """Test double for ultralytics YOLO model.

    Implements the minimal interface required by ObjectDetector:
    - __init__(model_path) -> None
    - predict(source, **kwargs) -> List[FakeResult]
    - names: dict[int, str] - class ID to name mapping

    Usage:
        yolo = FakeYOLO()
        yolo.set_pred([result1, result2])
        predictions = yolo.predict(frame)
    """

    def __init__(self, model_path: str | None = None):
        """Initialize the dummy YOLO model.

        Args:
            model_path: Path to model file (accepted but unused in tests)
        """
        # model_path is accepted to match the ultralytics API signature
        # but isn't used by this test double
        del model_path
        self.names = {0: "person", 1: "cat", 2: "dog"}
        self._pred: list[FakeResult] = []

    def set_pred(self, results: list[FakeResult]) -> None:
        """Configure the prediction results to return.

        Args:
            results: List of FakeResult objects to return from predict()
        """
        self._pred = results

    def predict(self, source: Any = None, **kwargs: Any) -> list[FakeResult]:
        """Return preconfigured prediction results.

        This is synchronous and deterministic for testing, unlike the real
        YOLO model which performs actual inference.

        Args:
            source: Image source (accepted but unused)
            **kwargs: Additional parameters (accepted but unused)

        Returns:
            List of FakeResult objects previously set via set_pred()
        """
        # Accept and discard parameters to match the real signature
        del source, kwargs
        return self._pred


class ErrYOLO(FakeYOLO):
    """YOLO variant that raises exceptions for error testing.

    Useful for testing error handling paths in the ObjectDetector.
    """

    def __init__(self, error_type: type = ValueError, error_msg: str = "Test error"):
        """Initialize with configurable error.

        Args:
            error_type: Type of exception to raise
            error_msg: Error message to use
        """
        super().__init__()
        self.error_type = error_type
        self.error_msg = error_msg

    def predict(self, source: Any = None, **kwargs: Any) -> list[FakeResult]:
        """Raise configured exception instead of returning results.

        Args:
            source: Image source (unused)
            **kwargs: Additional parameters (unused)

        Raises:
            Exception of type self.error_type with self.error_msg
        """
        raise self.error_type(self.error_msg)


@dataclass
class DetectionSpec:
    """Specification for a single detection."""

    cls_id: int
    bbox: list[float]
    confidence: float
    label: str


class DetectionBuilder:
    """Fluent builder for creating test detection data."""

    def __init__(self):
        """Initialize an empty detection builder."""
        self._specs: list[DetectionSpec] = []

    def add_detection(
        self, label_id: int, bbox: list[float], confidence: float, label: str = ""
    ) -> DetectionBuilder:
        """Add a detection to the builder."""
        spec = DetectionSpec(
            cls_id=label_id, bbox=bbox, confidence=confidence, label=label
        )
        self._specs.append(spec)
        return self

    def add_spec(self, spec: DetectionSpec) -> DetectionBuilder:
        """Add a detection from a spec."""
        self._specs.append(spec)
        return self

    def add_specs(self, specs: list[DetectionSpec]) -> DetectionBuilder:
        """Add multiple detections from specs."""
        self._specs.extend(specs)
        return self

    @property
    def specs(self) -> list[DetectionSpec]:
        """Get the specs that were added."""
        return self._specs

    def build(self, orig_shape: tuple[int, int] = (480, 640)) -> FakeResult:
        """Build the final FakeResult object."""
        if self._specs:
            cls_vals = [spec.cls_id for spec in self._specs]
            xyxy_vals = [spec.bbox for spec in self._specs]
            conf_vals = [spec.confidence for spec in self._specs]
            names_map = {spec.cls_id: spec.label for spec in self._specs if spec.label}
        else:
            cls_vals, xyxy_vals, conf_vals, names_map = [], [], [], {}

        boxes = FakeBoxes(cls_vals, xyxy_vals, conf_vals)
        return FakeResult(names_map, boxes, orig_shape)


class FakeViseron:
    """Minimal fake Viseron instance for testing.

    Provides the minimal interface needed by ObjectDetector without
    requiring the full Viseron application.
    """

    def __init__(self):
        """Initialize with empty state."""
        self.registered_domains: list[tuple[str, str, Any]] = []

    def register_domain(self, domain: str, identifier: str, instance: Any):
        """Record domain registration for verification in tests.

        Args:
            domain: Domain name being registered
            identifier: Camera or component identifier
            instance: The instance being registered
        """
        self.registered_domains.append((domain, identifier, instance))


class FakeCamera:
    """Minimal camera object for testing.

    Provides resolution and identifier attributes needed by ObjectDetector.
    """

    def __init__(self, identifier: str, resolution: tuple[int, int] = (640, 480)):
        """Initialize fake camera.

        Args:
            identifier: Unique camera identifier
            resolution: Camera resolution as (width, height)
        """
        self.identifier = identifier
        self.resolution = resolution
