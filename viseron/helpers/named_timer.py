"""Helper class to have named timers."""

from threading import Timer


class NamedTimer(Timer):
    """Helper class to have named timers."""

    def __init__(
        self, interval, function, name=None, daemon=None, args=None, kwargs=None
    ):
        super().__init__(interval, function, args, kwargs)
        self.name = name
        if daemon is not None:
            self.daemon = daemon
