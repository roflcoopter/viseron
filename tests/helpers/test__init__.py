"""Test helpers module."""
from contextlib import nullcontext

import pytest

from viseron import helpers


@pytest.mark.parametrize(
    "frame_res, model_res, bbox, expected, raises, message",
    [
        (
            (1920, 1080),
            (300, 300),
            (75, 90, 105, 120),
            (0.25, 0.144, 0.35, 0.322),
            nullcontext(),
            None,
        ),
        (
            (1080, 1920),
            (300, 300),
            (75, 90, 105, 120),
            (0.056, 0.3, 0.233, 0.4),
            nullcontext(),
            None,
        ),
        (
            (640, 360),
            (640, 640),
            (10, 320, 10, 320),
            (0.016, 0.5, 0.016, 0.5),
            nullcontext(),
            None,
        ),
        (
            (640, 360),
            (640, 640),
            (10, 140, 10, 140),
            (0.016, 0.0, 0.016, 0.0),
            nullcontext(),
            None,
        ),
        (
            (360, 640),
            (640, 640),
            (320, 5, 320, 5),
            (0.5, 0.008, 0.5, 0.008),
            nullcontext(),
            None,
        ),
        (
            (360, 640),
            (640, 640),
            (140, 5, 140, 5),
            (0.0, 0.008, 0.0, 0.008),
            nullcontext(),
            None,
        ),
        (
            (0, 0),
            (600, 640),
            (0, 0, 0, 0),
            (0, 0, 0, 0),
            pytest.raises(ValueError),
            (
                "Can only convert bbox from a letterboxed image "
                "for models of equal width and height, got 600x640"
            ),
        ),
    ],
)
def test_convert_letterboxed_bbox(
    frame_res, model_res, bbox, expected, raises, message
):
    """Test convert_letterboxed_bbox."""
    with raises as exception:
        converted_bbox = helpers.convert_letterboxed_bbox(
            frame_res[0], frame_res[1], model_res[0], model_res[1], bbox
        )
        assert converted_bbox == expected
    if message:
        assert str(exception.value) == message
