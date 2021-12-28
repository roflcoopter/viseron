"""Helper class of Popen that uses a lock.

The reason why this is needed is because of this issue:
https://github.com/opencv/opencv/issues/19643

Without it, darknet object detection will "freeze" and the output detections will hang
and always return the same result.
"""
import subprocess as sp
from threading import Lock

POPEN_LOCK = Lock()


def run(
    *args,
    **kwargs,
):
    """subprocess.run method using a lock."""
    with POPEN_LOCK:
        return sp.run(  # pylint: disable=subprocess-run-check
            *args,
            **kwargs,
        )


class Popen(sp.Popen):
    """Start Popen with a lock."""

    def __init__(self, *args, **kwargs):
        with POPEN_LOCK:
            super().__init__(*args, **kwargs)
