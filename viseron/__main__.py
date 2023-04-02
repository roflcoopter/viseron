"""Start Viseron."""
import signal
import sys

from viseron import setup_viseron


def main():
    """Start Viseron."""
    viseron = None

    def signal_term(*_) -> None:
        if viseron:
            viseron.shutdown()

    # Listen to signals
    signal.signal(signal.SIGTERM, signal_term)
    signal.signal(signal.SIGINT, signal_term)

    viseron = setup_viseron()

    signal.pause()
    return viseron.exit_code


def init():
    """Initialize."""
    if __name__ == "__main__":
        return main()
    return 1


sys.exit(init())
