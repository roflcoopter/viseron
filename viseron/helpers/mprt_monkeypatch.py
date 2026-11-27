"""Monkey-patch multiprocessing.resource_tracker so SharedMemory won't be tracked."""

from multiprocessing import resource_tracker


def remove_shm_from_resource_tracker() -> None:
    """Monkey-patch multiprocessing.resource_tracker so SharedMemory won't be tracked.

    More details at: https://bugs.python.org/issue38119
    """

    # pylint: disable=protected-access
    def fix_register(name, rtype):
        if rtype == "shared_memory":
            return
        return resource_tracker._resource_tracker.register(name, rtype)

    resource_tracker.register = fix_register

    def fix_unregister(name, rtype):
        if rtype == "shared_memory":
            return
        return resource_tracker._resource_tracker.unregister(name, rtype)

    resource_tracker.unregister = fix_unregister

    if "shared_memory" in resource_tracker._CLEANUP_FUNCS:  # type: ignore[attr-defined]
        del resource_tracker._CLEANUP_FUNCS[  # type: ignore[attr-defined]
            "shared_memory"
        ]
