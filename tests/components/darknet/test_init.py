"""Darknet component tests."""

from __future__ import annotations

from queue import Empty
from unittest.mock import MagicMock, patch

import pytest

from viseron.components import darknet as darknet_component
from viseron.components.darknet import DarknetDNN, DarknetNative, LoadDarknetError
from viseron.components.darknet.const import (
    CONFIG_HALF_PRECISION,
    CONFIG_MODEL_CONFIG,
    CONFIG_MODEL_PATH,
)


def _init_base_darknet(darknet, _vis, _config) -> None:
    darknet.labels = []
    darknet._model_width = 416
    darknet._model_height = 416


def test_native_stops_childon_init_timeout() -> None:
    """The worker must not keep running when the network fails to load.

    The setup is retried on LoadDarknetError, so a running worker would leak a child
    process that the watchdog restarts forever.
    """
    mp_context = MagicMock()
    mp_context.Event.return_value.wait.return_value = False
    with (
        patch.object(darknet_component.BaseDarknet, "__init__", _init_base_darknet),
        patch.object(DarknetNative, "create_data_file"),
        patch.object(darknet_component.ChildProcessWorker, "__init__"),
        patch.object(darknet_component.ChildProcessWorker, "stop") as mock_stop,
        patch.object(
            darknet_component, "get_child_process_context", return_value=mp_context
        ),
        pytest.raises(LoadDarknetError),
    ):
        DarknetNative(
            MagicMock(),
            {
                CONFIG_HALF_PRECISION: False,
                CONFIG_MODEL_CONFIG: "/model.cfg",
                CONFIG_MODEL_PATH: "/model.weights",
            },
        )

    mock_stop.assert_called_once()


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
