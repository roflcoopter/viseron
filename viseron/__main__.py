"""Start Viseron."""
import signal

from viseron import setup_viseron


def main():
    """Start Viseron."""
    viseron = setup_viseron()

    def signal_term(*_):
        viseron.shutdown()

    # Listen to signals
    signal.signal(signal.SIGTERM, signal_term)
    signal.signal(signal.SIGINT, signal_term)
    signal.pause()


def init():
    """Initialize."""
    if __name__ == "__main__":
        main()


init()
