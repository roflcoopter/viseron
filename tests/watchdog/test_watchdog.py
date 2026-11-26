"""Tests for the WatchDog base class."""

import threading

import pytest

from viseron.watchdog import WatchDog


class _DummyWatchDog(WatchDog):
    """Concrete watchdog for tests."""

    def watchdog(self):
        """Never runs in these tests."""


@pytest.fixture(name="watchdog_cls")
def watchdog_cls_fixture():
    """Provide a watchdog class with an isolated registry."""
    registry = type(
        "IsolatedWatchDog",
        (_DummyWatchDog,),
        {"registered_items": [], "started": True},
    )
    yield registry
    registry.registered_items = []


def test_stop_clears_class_registry(watchdog_cls):
    """stop() must clear the class-level registry that register() appends to.

    register/unregister are classmethods on cls.registered_items, so an
    instance attribute assignment in stop() only shadows the list for that
    one instance and leaves stale items in the shared registry.
    """
    watchdog = watchdog_cls()
    item = threading.Thread(target=lambda: None)
    watchdog_cls.register(item)
    assert watchdog_cls.registered_items == [item]

    watchdog.stop()

    assert watchdog_cls.registered_items == []
    assert watchdog.registered_items == []


def test_stop_does_not_affect_other_instances(watchdog_cls):
    """Stopping one watchdog clears the shared registry for all instances."""
    first = watchdog_cls()
    second = watchdog_cls()
    item = threading.Thread(target=lambda: None)
    watchdog_cls.register(item)

    first.stop()

    assert second.registered_items == []
