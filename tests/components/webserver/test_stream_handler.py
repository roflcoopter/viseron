"""Tests for StreamHandler."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from tornado.httputil import HTTPHeaders

from viseron.components.webserver.stream_handler import StreamHandler
from viseron.domains.camera.config import MJPEG_STREAM_SCHEMA

LABELS = {"a": "person", "b": "person", "c": "dog"}


@pytest.mark.parametrize(
    ("draw_objects", "in_fov", "in_zones", "expected"),
    [
        (True, [], [["a"]], ["a"]),
        (True, ["a"], [["b", "a"], ["c", "b"]], ["a", "b", "c"]),
        (True, [], [[], []], None),
        (False, ["a"], [["b"]], None),
    ],
)
def test_process_frame_draws_objects(
    draw_objects: bool,
    in_fov: list[str],
    in_zones: list[list[str]],
    expected: list[str] | None,
) -> None:
    """Objects in the field of view and in zones are drawn once, fov first."""
    objects = {name: MagicMock(label=label) for name, label in LABELS.items()}
    nvr = MagicMock()
    nvr.camera.shared_frames.get_decoded_frame_rgb.return_value = np.zeros(
        (2, 2, 3), np.uint8
    )
    nvr.camera.resolution = (2, 2)
    nvr.motion_detector = None
    nvr.post_processors = {}
    nvr.object_detector.mask = []
    nvr.object_detector.zones = [
        MagicMock(objects_in_zone=[objects[name] for name in names])
        for names in in_zones
    ]
    processed_frame = MagicMock(objects_in_fov=[objects[name] for name in in_fov])
    config = MJPEG_STREAM_SCHEMA({"draw_zones": False, "draw_objects": draw_objects})

    with patch("viseron.components.webserver.stream_handler.draw_objects") as draw:
        StreamHandler.process_frame(nvr, processed_frame, config)

    if expected is None:
        draw.assert_not_called()
    else:
        draw.assert_called_once()
        assert draw.call_args.args[1] == [objects[name] for name in expected]
        assert draw.call_args.kwargs == {"resolution": (2, 2)}
        assert processed_frame.objects_in_fov == [objects[name] for name in in_fov]


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        pytest.param(
            {}, "multipart/x-mixed-replace; boundary=jpgboundary", id="no_accept"
        ),
        pytest.param(
            {"Accept": "application/octet-stream"},
            "application/octet-stream",
            id="frontend_fetch",
        ),
    ],
)
def test_set_stream_headers_content_type(
    headers: dict[str, str], expected: str
) -> None:
    """Multipart is the default, octet-stream is served when explicitly accepted."""
    handler = MagicMock()
    handler.request.headers = HTTPHeaders(headers)

    StreamHandler._set_stream_headers(handler)

    handler.set_header.assert_any_call("Content-Type", expected)
