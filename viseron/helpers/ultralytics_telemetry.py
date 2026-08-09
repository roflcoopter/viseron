"""Helpers for the third-party ultralytics package."""

from ultralytics import settings


def disable_ultralytics_telemetry() -> None:
    """Disable ultralytics' built-in analytics and crash reporting.

    The upstream ultralytics package ships Google Analytics event collection
    and Sentry crash reporting, controlled by the persisted ``sync`` setting
    which defaults to enabled. Per the ultralytics documentation, persisting
    ``sync = False`` opts out of both.

    The setting is read at ultralytics import time, so this takes full effect
    from the next process start. On the very first run after a fresh install
    the in-process telemetry instance may have latched its enabled flag before
    this call; that single-process window is accepted as negligible.
    """
    settings.update({"sync": False})
