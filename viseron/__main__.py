"""Start Viseron."""
import signal

from viseron import setup_viseron


def main():
    """Start Viseron."""
    viseron = None

    def signal_term(*_):
        if viseron:
            viseron.shutdown()

    # Listen to signals
    signal.signal(signal.SIGTERM, signal_term)
    signal.signal(signal.SIGINT, signal_term)

    viseron = setup_viseron()

    signal.pause()


def init():
    """Initialize."""
    if __name__ == "__main__":
        main()


init()
