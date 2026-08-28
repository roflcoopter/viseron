"""Tests for shared frames."""

from __future__ import annotations

import weakref
from collections import deque
from typing import TYPE_CHECKING

import numpy as np
import pytest

from viseron.domains.camera.shared_frames import (
    COLOR_MODEL_GRAY,
    COLOR_MODEL_RGB,
    PIXEL_FORMAT_YUV420P,
    SharedFrame,
    SharedFrames,
)

if TYPE_CHECKING:
    from collections.abc import Callable

WIDTH = 32
HEIGHT = 32
COLOR_PLANE_HEIGHT = HEIGHT * 3 // 2
FRAME_BYTES = b"\x00" * (WIDTH * COLOR_PLANE_HEIGHT)


def _create_frame() -> SharedFrame:
    """Return a frame holding FRAME_BYTES."""
    return SharedFrame(
        FRAME_BYTES,
        WIDTH,
        COLOR_PLANE_HEIGHT,
        PIXEL_FORMAT_YUV420P,
        (WIDTH, HEIGHT),
        "test_camera_identifier",
    )


@pytest.fixture(name="shared_frame")
def fixture_shared_frame() -> SharedFrame:
    """Return a frame holding FRAME_BYTES."""
    return _create_frame()


class TestLifetime:
    """Tests for the lifetime of the memory a frame holds.

    A frame is owned by the SharedFrame object, so frames that never reach a
    consumer, such as the ones dropped by a full subscriber queue, are freed
    along with the object instead of being held forever.
    """

    def test_frame_is_freed_once_it_is_dropped(self) -> None:
        """Nothing outlives the last reference to a frame."""
        shared_frame = _create_frame()
        shared_frame.color_convert(COLOR_MODEL_RGB)
        reference = weakref.ref(shared_frame)

        del shared_frame

        assert reference() is None

    def test_frame_dropped_by_a_full_queue_is_freed(self) -> None:
        """A frame evicted from a full consumer queue is freed, a queued one is not."""
        queue: deque[SharedFrame] = deque(maxlen=1)

        dropped = _create_frame()
        queue.append(dropped)
        dropped_reference = weakref.ref(dropped)
        del dropped

        queued = _create_frame()
        queue.append(queued)
        queued_reference = weakref.ref(queued)
        del queued

        assert dropped_reference() is None
        assert queued_reference() is not None


class TestColorConvert:
    """Tests for color conversion of a frame."""

    @pytest.mark.parametrize(
        ("color_model", "expected_shape"),
        [
            pytest.param(COLOR_MODEL_RGB, (HEIGHT, WIDTH, 3), id="rgb"),
            pytest.param(COLOR_MODEL_GRAY, (HEIGHT, WIDTH), id="gray"),
        ],
    )
    def test_color_convert(
        self,
        shared_frame: SharedFrame,
        color_model: str,
        expected_shape: tuple[int, ...],
    ) -> None:
        """A frame is converted to the requested color model."""
        assert shared_frame.color_convert(color_model).shape == expected_shape

    def test_color_convert_is_cached(self, shared_frame: SharedFrame) -> None:
        """A frame is only converted once per color model."""
        assert shared_frame.color_convert(COLOR_MODEL_RGB) is (
            shared_frame.color_convert(COLOR_MODEL_RGB)
        )

    def test_decoded_frame_is_not_copied(self, shared_frame: SharedFrame) -> None:
        """The undecoded frame is handed out as is."""
        assert (
            SharedFrames.get_decoded_frame(shared_frame) is shared_frame.decoded_frame
        )

    @pytest.mark.parametrize(
        ("get_frame", "color_model"),
        [
            pytest.param(SharedFrames.get_decoded_frame_rgb, COLOR_MODEL_RGB, id="rgb"),
            pytest.param(
                SharedFrames.get_decoded_frame_gray, COLOR_MODEL_GRAY, id="gray"
            ),
        ],
    )
    def test_converted_frames_are_copies(
        self,
        shared_frame: SharedFrame,
        get_frame: Callable[[SharedFrame], np.ndarray],
        color_model: str,
    ) -> None:
        """Consumers get a copy so their edits don't leak into the cached frame."""
        frame = get_frame(shared_frame)
        frame[:] = 255

        assert not np.array_equal(frame, get_frame(shared_frame))
        assert not np.array_equal(frame, shared_frame.color_convert(color_model))
