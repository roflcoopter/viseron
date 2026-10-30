"""Tests for viseron.components.hailo.hailo_process."""

from __future__ import annotations

from viseron.components import hailo
from viseron.components.hailo.hailo_process import Hailo8Work
from viseron.helpers.child_process_context import get_child_process_context

from tests.common import pickle_for_child_process


def _work() -> Hailo8Work:
    mp_context = get_child_process_context()
    return Hailo8Work(
        "/model.hef",
        multi_process_service=True,
        initialization_done=mp_context.Event(),
        initialization_error=mp_context.Event(),
    )


def test_work_is_picklable() -> None:
    """The work crosses a forkserver boundary, so it must pickle.

    The Hailo device can't be pickled, so it must not be opened until the work is
    initialized inside the child process.
    """
    restored = pickle_for_child_process(_work())
    assert restored._model_path == "/model.hef"


def test_logger_names_belong_to_the_hailo_component() -> None:
    """Log levels configured for the hailo component must reach the child."""
    for logger_name in _work().logger_names:
        assert logger_name.startswith(f"{hailo.__name__}.")
