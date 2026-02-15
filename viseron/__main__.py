"""Start Viseron."""
from __future__ import annotations

import logging
import multiprocessing as mp
import os
import signal
import sys
import threading

from viseron import Viseron, enable_logging, setup_viseron
from viseron.helpers import kill_zombie_processes
from viseron.helpers.named_timer import NamedTimer

LOGGER = logging.getLogger("viseron.main")


def main():
    """Start Viseron."""
    viseron: Viseron | None = None
    shutdown_thread: threading.Thread | None = None

    def signal_term(*_) -> None:
        """Start viseron.shutdown() on a daemon thread to not block the MainThread."""
        nonlocal shutdown_thread
        if viseron and shutdown_thread is None:
            shutdown_thread = threading.Thread(
                target=viseron.shutdown, name="viseron_shutdown", daemon=True
            )
            shutdown_thread.start()

    # Listen to signals
    signal.signal(signal.SIGTERM, signal_term)
    signal.signal(signal.SIGINT, signal_term)

    viseron = Viseron()
    enable_logging()
    kill_zombie_processes()
    setup_viseron(viseron)

    # Keep the process alive until a signal is received.
    if not viseron.shutdown_event.is_set():
        signal.pause()

    # Wait for the shutdown thread to finish if it was started by the signal
    if shutdown_thread is not None:
        shutdown_thread.join()

    def shutdown_failed():
        LOGGER.debug("Shutdown failed. Exiting forcefully.")
        LOGGER.debug(f"Active threads: {threading.enumerate()}")
        LOGGER.debug(f"Active processes: {mp.active_children()}")
        os.kill(os.getpid(), signal.SIGKILL)

    LOGGER.debug(f"Active threads: {threading.enumerate()}")
    shutdown_timer = NamedTimer(2, shutdown_failed, name="ShutdownTimer")
    shutdown_timer.daemon = True
    shutdown_timer.start()

    if viseron:
        return viseron.exit_code
    return 0


def init():
    """Initialize."""
    if __name__ == "__main__":
        return main()
    return 1


sys.exit(init())
