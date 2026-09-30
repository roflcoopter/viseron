"""Tests for the notification helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from viseron.exceptions import DomainNotRegisteredError
from viseron.helpers.notifications import (
    future_datetime,
    notifications_configured,
    notifications_paused,
    register_notification_cameras,
    unregister_notification_cameras,
)


def _vis_with_cameras(cameras: dict[str, MagicMock]) -> MagicMock:
    vis = MagicMock()
    vis.get_registered_identifiers.return_value = cameras
    return vis


def test_paused_camera() -> None:
    """A paused camera is reported as paused."""
    vis = _vis_with_cameras({"cam": MagicMock(notifications_paused=True)})
    assert notifications_paused(vis, "cam") is True


def test_unpaused_camera() -> None:
    """A camera that is not paused is reported as not paused."""
    vis = _vis_with_cameras({"cam": MagicMock(notifications_paused=False)})
    assert notifications_paused(vis, "cam") is False


def test_unknown_camera() -> None:
    """An unknown camera is never paused."""
    vis = _vis_with_cameras({"cam": MagicMock(notifications_paused=True)})
    assert notifications_paused(vis, "other") is False


def test_no_camera() -> None:
    """An event without a camera is never paused."""
    vis = _vis_with_cameras({"cam": MagicMock(notifications_paused=True)})
    assert notifications_paused(vis, None) is False
    vis.get_registered_identifiers.assert_not_called()


def test_camera_domain_not_registered() -> None:
    """No cameras loaded means nothing is paused."""
    vis = MagicMock()
    vis.get_registered_identifiers.side_effect = DomainNotRegisteredError("camera")
    assert notifications_paused(vis, "cam") is False


def test_notifications_configured() -> None:
    """Cameras are configured while a notification component registers them."""
    vis = MagicMock(data={})
    assert notifications_configured(vis, "cam") is False

    register_notification_cameras(vis, "discord", ["cam"])
    register_notification_cameras(vis, "gotify", ["cam", "other"])
    assert notifications_configured(vis, "cam") is True
    assert notifications_configured(vis, "other") is True

    unregister_notification_cameras(vis, "gotify")
    assert notifications_configured(vis, "cam") is True
    assert notifications_configured(vis, "other") is False


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "value",
    ["2026-01-01T11:00:00Z", "2026-01-01T13:00:00", "tomorrow", 3600],
)
def test_future_datetime_invalid(value) -> None:
    """Past, naive and malformed datetimes are rejected."""
    with (
        patch("viseron.helpers.notifications.utcnow", return_value=NOW),
        pytest.raises(vol.Invalid),
    ):
        future_datetime(value)


def test_future_datetime() -> None:
    """A timezone aware datetime in the future is parsed."""
    with patch("viseron.helpers.notifications.utcnow", return_value=NOW):
        assert future_datetime("2026-01-01T13:00:00Z") == NOW + timedelta(hours=1)
