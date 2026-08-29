"""Modules preloaded into the multiprocessing forkserver.

Importing any ``viseron.*`` submodule executes ``viseron/__init__.py``, which pulls
in roughly a lot of dependencies. Preloading the child entrypoints means every child
shares that copy-on-write instead of importing a private copy after forking.
Only works together with ``gc.freeze()`` in the child.
"""

import importlib
import logging

LOGGER = logging.getLogger(__name__)

PRELOAD_MODULES = (
    "viseron.components.ffmpeg.frame_reader",
    "viseron.components.gstreamer.gst_process",
)


def preload() -> None:
    """Import the child process entrypoint modules, ignoring failures."""
    for module in PRELOAD_MODULES:
        try:
            importlib.import_module(module)
        except Exception:  # pylint: disable=broad-except # noqa: BLE001
            LOGGER.debug(f"Could not preload {module}", exc_info=True)


preload()
