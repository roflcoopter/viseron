"""Start Viseron."""
from __future__ import annotations

import logging
import multiprocessing as mp
import os
import signal
import sys
import threading
from threading import Timer

from viseron import Viseron, enable_logging, setup_viseron
from viseron.helpers import kill_zombie_processes

LOGGER = logging.getLogger("viseron.main")


def main():
    """Start Viseron."""
    viseron: Viseron | None = None

    def signal_term(*_) -> None:
        if viseron:
            viseron.shutdown()

        def shutdown_failed():
            LOGGER.debug("Shutdown failed. Exiting forcefully.")
            LOGGER.debug(f"Active threads: {threading.enumerate()}")
            LOGGER.debug(f"Active processes: {mp.active_children()}")
            os.kill(os.getpid(), signal.SIGKILL)

        LOGGER.debug(f"Active threads: {threading.enumerate()}")
        shutdown_timer = Timer(2, shutdown_failed, args=())
        shutdown_timer.daemon = True
        shutdown_timer.start()

    # Listen to signals
    signal.signal(signal.SIGTERM, signal_term)
    signal.signal(signal.SIGINT, signal_term)

    viseron = Viseron()
    enable_logging()
    kill_zombie_processes()
    setup_viseron(viseron)

    signal.pause()
    if viseron:
        return viseron.exit_code
    return 0


def init():
    """Initialize."""
    if __name__ == "__main__":
        return main()
    return 1


sys.exit(init())
