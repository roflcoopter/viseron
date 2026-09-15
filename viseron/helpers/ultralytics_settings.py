"""Helpers for the third-party ultralytics package."""

import os

from ultralytics import settings

from viseron.const import TEMP_DIR


def set_ultralytics_settings() -> None:
    """Update Ultralytics settings globally.

    ``sync = False`:
        Disable ultralytics' built-in analytics and crash reporting.

        The upstream ultralytics package ships Google Analytics event collection
        and Sentry crash reporting, controlled by the persisted ``sync`` setting
        which defaults to enabled. Per the ultralytics documentation, persisting
        ``sync = False`` opts out of both.

    ``runs_dir``:
        Sets a writable path so Ultralytics works when running as a non-root user.
    """
    settings.update(
        {
            "sync": False,
            "runs_dir": os.path.join(TEMP_DIR, "ultralytics"),
        }
    )
