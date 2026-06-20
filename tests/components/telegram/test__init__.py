"""Tests for the Telegram component."""

from __future__ import annotations

import asyncio
import datetime
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

from viseron.components.storage.models import TriggerTypes
from viseron.components.telegram import TelegramEventNotifier
from viseron.components.telegram.const import (
    CONFIG_CAMERAS,
    CONFIG_DETECTION_LABEL,
    CONFIG_SEND_MESSAGE,
    CONFIG_SEND_THUMBNAIL,
    CONFIG_SEND_VIDEO,
    CONFIG_TELEGRAM_BOT_TOKEN,
    CONFIG_TELEGRAM_CHAT_IDS,
    CONFIG_TELEGRAM_USER_IDS,
)
from viseron.domains.camera.const import EVENT_RECORDER_COMPLETE
from viseron.domains.camera.recorder import EventRecorderData, Recording
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.events import Event

CAMERA_IDENTIFIER = "camera_1"
CHAT_ID = 1234
FRAME_RES = (1920, 1080)


def create_detected_object(label: str) -> DetectedObject:
    """Create a detected object."""
    return DetectedObject(label, 0.9, 0.1, 0.1, 0.2, 0.2, FRAME_RES)


def create_event(labels: list[str]) -> Event[EventRecorderData]:
    """Create a recorder complete event."""
    start_time = datetime.datetime(2026, 6, 20, 12, tzinfo=datetime.timezone.utc)
    camera = MagicMock(identifier=CAMERA_IDENTIFIER)
    recording = Recording(
        id=1,
        start_time=start_time,
        start_timestamp=start_time.timestamp(),
        end_time=start_time + datetime.timedelta(seconds=5),
        end_timestamp=start_time.timestamp() + 5,
        date="2026-06-20",
        thumbnail=None,
        thumbnail_path="/tmp/thumbnail.jpg",
        clip_path="/tmp/clip.mp4",
        objects=[create_detected_object(label) for label in labels],
        trigger_type=TriggerTypes.OBJECT,
    )
    return Event(
        name=EVENT_RECORDER_COMPLETE.format(camera_identifier=CAMERA_IDENTIFIER),
        data=EventRecorderData(camera=camera, recording=recording),
        timestamp=start_time.timestamp(),
    )


def create_notifier() -> TelegramEventNotifier:
    """Create a Telegram notifier with mocked Telegram clients."""
    vis = MagicMock()
    vis.data = {}
    vis.listen_event.return_value = lambda: None
    vis.register_signal_handler.return_value = lambda: None
    bot = MagicMock()
    bot.send_video = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.send_message = AsyncMock()
    app = MagicMock()
    builder = MagicMock()
    builder.token.return_value.build.return_value = app

    config = {
        CONFIG_TELEGRAM_BOT_TOKEN: "token",
        CONFIG_TELEGRAM_CHAT_IDS: [CHAT_ID],
        CONFIG_TELEGRAM_USER_IDS: [],
        CONFIG_DETECTION_LABEL: "person",
        CONFIG_SEND_VIDEO: True,
        CONFIG_SEND_THUMBNAIL: True,
        CONFIG_SEND_MESSAGE: True,
        CONFIG_CAMERAS: {CAMERA_IDENTIFIER: {}},
    }

    with (
        patch("viseron.components.telegram.Bot", return_value=bot),
        patch("viseron.components.telegram.Application.builder", return_value=builder),
    ):
        notifier = TelegramEventNotifier(vis, config)

    return notifier


def close_notifier(notifier: TelegramEventNotifier) -> None:
    """Close the notifier event loop."""
    notifier._loop.close()
    notifier._sensitive_string_tracker.clear_sensitive_strings()


async def send_notifications(
    notifier: TelegramEventNotifier,
    event_data: Event[EventRecorderData],
) -> None:
    """Send notifications with filesystem and image operations mocked."""
    with (
        patch("viseron.components.telegram.os.path.exists", return_value=True),
        patch(
            "viseron.components.telegram.rescale_image_cv2",
            return_value="/tmp/rescaled.jpg",
        ),
        patch("builtins.open", mock_open(read_data=b"data")),
    ):
        await notifier._send_notifications(event_data)


def assert_notifications_sent(notifier: TelegramEventNotifier) -> None:
    """Assert all configured notification types were sent."""
    notifier._bot.send_video.assert_awaited_once()
    notifier._bot.send_photo.assert_awaited_once()
    notifier._bot.send_message.assert_awaited_once()


def assert_notifications_skipped(notifier: TelegramEventNotifier) -> None:
    """Assert no configured notification type was sent."""
    notifier._bot.send_video.assert_not_awaited()
    notifier._bot.send_photo.assert_not_awaited()
    notifier._bot.send_message.assert_not_awaited()


def test_sends_notification_when_detection_label_matches() -> None:
    """Test that notifications are sent when the recording has the configured label."""
    notifier = create_notifier()

    try:
        asyncio.run(send_notifications(notifier, create_event(["person"])))

        assert_notifications_sent(notifier)
    finally:
        close_notifier(notifier)


def test_skips_notification_when_detection_label_does_not_match() -> None:
    """Test that notifications are skipped when the recording has a different label."""
    notifier = create_notifier()

    try:
        asyncio.run(send_notifications(notifier, create_event(["car"])))

        assert_notifications_skipped(notifier)
    finally:
        close_notifier(notifier)


def test_skips_notification_when_recording_has_no_objects() -> None:
    """Test that notifications are skipped when the recording has no objects."""
    notifier = create_notifier()

    try:
        asyncio.run(send_notifications(notifier, create_event([])))

        assert_notifications_skipped(notifier)
    finally:
        close_notifier(notifier)


def test_sends_notification_when_any_object_matches_detection_label() -> None:
    """Test that notifications are sent when any recorded object has the label."""
    notifier = create_notifier()

    try:
        asyncio.run(send_notifications(notifier, create_event(["car", "person"])))

        assert_notifications_sent(notifier)
    finally:
        close_notifier(notifier)
