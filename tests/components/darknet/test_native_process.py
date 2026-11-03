"""Tests for viseron.components.darknet.native_process."""

from __future__ import annotations

from viseron.components import darknet
from viseron.components.darknet.native_process import (
    LIBDARKNET_LOGGER_NAME,
    DarknetNativeWork,
)
from viseron.helpers.child_process_context import get_child_process_context

from tests.common import pickle_for_child_process


def test_work_is_picklable() -> None:
    """The work crosses a forkserver boundary, so it must pickle.

    The Darknet library can't be pickled, so it must not be loaded until the work is
    initialized inside the child process.
    """
    restored = pickle_for_child_process(
        DarknetNativeWork(
            half_precision=False,
            model_config="/model.cfg",
            data_path="/darknet_data.data",
            model_path="/model.weights",
            model_width=416,
            model_height=416,
            initialization_done=get_child_process_context().Event(),
        )
    )
    assert restored._model_path == "/model.weights"
    assert restored.logger_names == (LIBDARKNET_LOGGER_NAME,)


def test_libdarknet_logger_belongs_to_the_darknet_component() -> None:
    """Log levels configured for the darknet component must reach the child."""
    assert LIBDARKNET_LOGGER_NAME.startswith(f"{darknet.__name__}.")
