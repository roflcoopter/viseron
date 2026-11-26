"""Tests for the ThreadWatchDog."""

import threading
from unittest.mock import MagicMock

from viseron.watchdog.thread_watchdog import RestartableThread, ThreadWatchDog


def test_watchdog_does_not_restart_thread_that_failed_to_stop():
    """Test that a live thread is left alone after a failed poll stop.

    The non-poll branch skips threads that are still alive, but the poll
    branch used to fall through to the restart path when poll_target failed
    to end the thread, starting a second instance while the original kept
    running.
    """
    watchdog = ThreadWatchDog(MagicMock())
    stop_event = threading.Event()
    thread = RestartableThread(
        target=stop_event.wait,
        name="stuck-thread",
        poll_method=lambda: True,
        poll_target=lambda: None,
    )
    thread.start()
    try:
        watchdog.watchdog()

        assert thread.is_alive(), "the watchdog must not kill the thread"
        assert ThreadWatchDog.registered_items == [thread], (
            "a thread that failed to stop must not be replaced by a clone"
        )
    finally:
        stop_event.set()
        thread.join(timeout=10)
