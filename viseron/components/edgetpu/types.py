"""Types for the EdgeTPU component."""
from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from viseron.components.edgetpu import EdgeTPUClassification, EdgeTPUDetection


class EdgeTPUViseronData(TypedDict, total=False):
    """TypedDict for EdgeTPU Viseron data."""

    image_classification: EdgeTPUClassification
    object_detector: EdgeTPUDetection
