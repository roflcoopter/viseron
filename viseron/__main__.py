"""Start Viseron."""
from __future__ import annotations

import multiprocessing as mp
import os
import signal
import sys
import threading
from threading import Timer

from viseron import Viseron, setup_viseron


def main():
    """Start Viseron."""
    viseron: Viseron | None = None

    def signal_term(*_) -> None:
        if viseron:
            viseron.shutdown()

        def shutdown_failed():
            print("Shutdown failed. Exiting forcefully.")
            print(f"Active threads: {threading.enumerate()}")
            print(f"Active processes: {mp.active_children()}")
            os.kill(os.getpid(), signal.SIGKILL)

        shutdown_timer = Timer(2, shutdown_failed, args=())
        shutdown_timer.daemon = True
        shutdown_timer.start()

    # Listen to signals
    signal.signal(signal.SIGTERM, signal_term)
    signal.signal(signal.SIGINT, signal_term)

    viseron = setup_viseron()

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
