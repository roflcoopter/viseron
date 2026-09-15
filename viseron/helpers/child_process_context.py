"""Multiprocessing context used for long-running child processes.

Children are created with the ``forkserver`` start method instead of ``fork``.
``forkserver.ensure_running()`` fork+execs a fresh interpreter, so the snapshot
children fork from is clean no matter how much memory the main process is using or
when the child is created.

Note that multiprocessing primitives are context-bound: a Queue or Event created in
the fork context cannot be passed to a forkserver child. Anything shared with a child
must be created from the context returned here.
"""

from __future__ import annotations

import multiprocessing as mp
from typing import cast

CHILD_PROCESS_START_METHOD = "forkserver"

_PRELOAD_SET = False


def get_child_process_context() -> mp.context.ForkServerContext:
    """Return the multiprocessing context for long-running child processes."""
    global _PRELOAD_SET  # noqa: PLW0603  # pylint: disable=global-statement

    context = cast(
        "mp.context.ForkServerContext", mp.get_context(CHILD_PROCESS_START_METHOD)
    )
    if not _PRELOAD_SET:
        context.set_forkserver_preload(["viseron.helpers.child_process_preload"])
        _PRELOAD_SET = True
    return context
