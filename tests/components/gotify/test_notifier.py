"""Tests for the Gotify notifier."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from viseron.components.gotify import CONFIG_SCHEMA, GotifyEventNotifier
from viseron.components.gotify.const import COMPONENT
from viseron.domains.camera.recorder import EventRecorderData
from viseron.events import Event

CAMERA_ID = "test_camera"


def make_event(label: str = "person") -> Event[EventRecorderData]:
    """Build a recorder start event with one detected object."""
    camera = MagicMock()
    camera.identifier = CAMERA_ID
    recording = MagicMock(objects=[MagicMock(label=label)], thumbnail=None)
    return Event(
        name="test",
        data=EventRecorderData(camera=camera, recording=recording),
        timestamp=0.0,
    )


@pytest.fixture(name="notifier")
def fixture_notifier() -> Iterator[GotifyEventNotifier]:
    """Return a GotifyEventNotifier without its background thread."""
    config = CONFIG_SCHEMA(
        {
            COMPONENT: {
                "gotify_url": "http://gotify.local",
                "gotify_token": "token",
                "cameras": {CAMERA_ID: None},
            }
        }
    )[COMPONENT]
    with patch("viseron.components.gotify.RestartableThread"):
        notifier = GotifyEventNotifier(MagicMock(), config)
    yield notifier
    notifier._loop.close()


class TestNotificationsPaused:
    """Tests for skipping notifications while the camera is paused."""

    def test_start_event_skipped(self, notifier: GotifyEventNotifier) -> None:
        """No notification is scheduled for a paused camera."""
        with (
            patch(
                "viseron.components.gotify.notifications_paused", return_value=True
            ) as paused,
            patch(
                "viseron.components.gotify.asyncio.run_coroutine_threadsafe"
            ) as run_coroutine,
        ):
            notifier._recording_start_event_handler(make_event())

        paused.assert_called_once_with(notifier._vis, CAMERA_ID)
        run_coroutine.assert_not_called()

    def test_start_event_sent_when_not_paused(
        self, notifier: GotifyEventNotifier
    ) -> None:
        """A camera that is not paused still schedules its notification."""
        with (
            patch("viseron.components.gotify.notifications_paused", return_value=False),
            patch(
                "viseron.components.gotify.asyncio.run_coroutine_threadsafe"
            ) as run_coroutine,
        ):
            notifier._recording_start_event_handler(make_event())

        run_coroutine.assert_called_once()
        run_coroutine.call_args.args[0].close()
