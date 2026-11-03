"""EdgeTPU component tests."""

from __future__ import annotations

from queue import Empty
from unittest.mock import MagicMock

import pytest

from viseron.components.edgetpu import EdgeTPU


@pytest.mark.parametrize(
    ("get_side_effect", "expected"),
    [
        pytest.param([{"result": "detections"}], "detections", id="result"),
        pytest.param(Empty, None, id="no_result"),
    ],
)
def test_invoke_does_not_block_without_result(
    get_side_effect: list[dict[str, str]] | type[Empty], expected: str | None
) -> None:
    """invoke() gives up when the subprocess never answers."""
    edgetpu = MagicMock(_result_queues={})
    result_queue = MagicMock()
    result_queue.get.side_effect = get_side_effect

    result = EdgeTPU.invoke(edgetpu, MagicMock(), "camera", result_queue, (640, 480))

    assert result == expected
    result_queue.get.assert_called_once_with(timeout=3)
