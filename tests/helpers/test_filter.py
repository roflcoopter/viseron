"""Tests for filter module."""
import pytest

from viseron.config.config_object_detection import LabelConfig
from viseron.detector.detected_object import DetectedObject
from viseron.helpers.filter import Filter

LABEL_CONFIG = {
    "label": "person",
    "confidence": 0.5,
    "height_min": 0.2,
    "height_max": 0.5,
    "width_min": 0.2,
    "width_max": 0.5,
    "trigger_recorder": True,
    "require_motion": False,
    "post_processor": None,
}


@pytest.mark.usefixtures("nvr_config_full")
@pytest.mark.usefixtures("resolution")
class TestFilter:
    """Tests for Filter class."""

    @pytest.mark.parametrize(
        "detected_object, filter_reason",
        [
            (
                {
                    "label": "person",
                    "confidence": 0.7,
                    "x1": 0,
                    "y1": 0,
                    "x2": 0.3,
                    "y2": 0.3,
                },
                None,
            ),
            (
                {
                    "label": "person",
                    "confidence": 0.3,
                    "x1": 0,
                    "y1": 0,
                    "x2": 0.3,
                    "y2": 0.3,
                },
                "confidence",
            ),
            (
                {
                    "label": "person",
                    "confidence": 0.7,
                    "x1": 0,
                    "y1": 0,
                    "x2": 0.1,
                    "y2": 0.3,
                },
                "width",
            ),
            (
                {
                    "label": "person",
                    "confidence": 0.7,
                    "x1": 0,
                    "y1": 0,
                    "x2": 0.3,
                    "y2": 0.1,
                },
                "height",
            ),
            (
                {
                    "label": "person",
                    "confidence": 0.7,
                    "x1": 0.6,
                    "y1": 0.6,
                    "x2": 0.9,
                    "y2": 0.9,
                },
                "mask",
            ),
        ],
    )
    def test_filter_object(
        self, nvr_config_full, resolution, detected_object, filter_reason
    ):
        """Test that the object filtering is working."""
        object_filter = Filter(
            nvr_config_full,
            resolution,
            LabelConfig(LABEL_CONFIG),
        )
        obj = DetectedObject(**detected_object)
        object_filter.filter_object(obj)
        assert not obj.relevant
        assert obj.filter_hit == filter_reason
        assert object_filter.trigger_recorder == LABEL_CONFIG["trigger_recorder"]
        assert object_filter.require_motion == LABEL_CONFIG["require_motion"]
        assert object_filter.post_processor == LABEL_CONFIG["post_processor"]
