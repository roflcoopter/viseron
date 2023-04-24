"""Start Viseron."""
from __future__ import annotations

import signal
import sys

from viseron import Viseron, setup_viseron


def main():
    """Start Viseron."""
    viseron: Viseron | None = None

    def signal_term(*_) -> None:
        if viseron:
            viseron.shutdown()

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
