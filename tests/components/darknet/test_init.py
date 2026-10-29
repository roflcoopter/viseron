"""Darknet component tests."""

from __future__ import annotations

from queue import Empty
from unittest.mock import MagicMock

import pytest

from viseron.components.darknet import DarknetDNN


@pytest.mark.parametrize(
    ("get_side_effect", "expected"),
    [
        pytest.param([{"result": "detections"}], "detections", id="result"),
        pytest.param(Empty, None, id="no_result"),
    ],
)
def test_dnn_detect_does_not_block_without_result(
    get_side_effect: list[dict[str, str]] | type[Empty], expected: str | None
) -> None:
    """detect() gives up when the subprocess never answers."""
    darknet = MagicMock(_result_queues={})
    result_queue = MagicMock()
    result_queue.get.side_effect = get_side_effect

    result = DarknetDNN.detect(darknet, MagicMock(), "camera", result_queue, 0.5)

    assert result == expected
    result_queue.get.assert_called_once_with(timeout=3)
