"""Fixtures for data_stream tests."""

from __future__ import annotations

import asyncio
import threading
from queue import Empty
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from tornado.ioloop import IOLoop

from viseron.components.data_stream import DataStream

if TYPE_CHECKING:
    from collections.abc import Callable, Generator


def _reset_data_stream_state() -> None:
    """Clear the class level state shared by every DataStream instance."""
    DataStream.remove_all_subscriptions()
    for queue in (DataStream._data_queue, DataStream._signal_queue):
        while True:
            try:
                queue.get_nowait()
            except Empty:
                break


@pytest.fixture
def data_stream() -> Generator[DataStream, Any, None]:
    """Yield a running DataStream with isolated class level state."""
    _reset_data_stream_state()
    stream = DataStream(MagicMock())
    yield stream
    stream.stop()
    stream.join()
    _reset_data_stream_state()


@pytest.fixture
def stopped_data_stream() -> Generator[DataStream, Any, None]:
    """Yield a DataStream whose consumer thread has already exited.

    Lets a test fill the queues and drive the consumer by hand.
    """
    _reset_data_stream_state()
    stream = DataStream(MagicMock())
    stream.stop()
    stream.join()
    yield stream
    _reset_data_stream_state()


@pytest.fixture
def ioloop() -> Generator[IOLoop, Any, None]:
    """Yield a Tornado IOLoop running in a background thread."""
    started = threading.Event()
    loop: dict[str, IOLoop] = {}

    def _run() -> None:
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop["ioloop"] = IOLoop.current()
        started.set()
        loop["ioloop"].start()

    thread = threading.Thread(target=_run, daemon=True, name="test_ioloop")
    thread.start()
    assert started.wait(timeout=5)

    yield loop["ioloop"]

    loop["ioloop"].add_callback(loop["ioloop"].stop)
    thread.join(timeout=5)


@pytest.fixture
def wait_for() -> Callable[..., None]:
    """Return a helper that blocks until an event fires, failing the test if not."""

    def _wait_for(event: threading.Event, timeout: float = 5) -> None:
        assert event.wait(timeout=timeout), "Timed out waiting for delivery"

    return _wait_for
