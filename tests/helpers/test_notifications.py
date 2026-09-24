"""Tests for the notification helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from viseron.exceptions import DomainNotRegisteredError
from viseron.helpers.notifications import notifications_paused


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
