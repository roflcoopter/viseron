"""Tests for DiscordNotifier detection_label filtering."""

from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import ANY, MagicMock, call, mock_open, patch

import pytest
import requests
import voluptuous as vol

from viseron.components.discord import CONFIG_SCHEMA, DiscordNotifier, setup, unload
from viseron.components.discord.const import (
    COMPONENT,
    CONFIG_CAMERAS,
    CONFIG_DETECTION_LABEL,
    CONFIG_DETECTION_LABELS,
    CONFIG_DISCORD_WEBHOOK_URL,
    CONFIG_MAX_VIDEO_SIZE_MB,
    CONFIG_MAX_VIDEO_SIZE_MB_DEFAULT,
    CONFIG_SEND_THUMBNAIL,
    CONFIG_SEND_VIDEO,
    DEFAULT_DETECTION_LABELS,
)
from viseron.components.storage.models import TriggerTypes
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera.const import EVENT_RECORDER_COMPLETE, EVENT_RECORDER_START
from viseron.domains.camera.recorder import EventRecorderData, Recording
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.events import Event
from viseron.helpers.validators import UNDEFINED

if TYPE_CHECKING:
    from tests.conftest import MockViseron

CAMERA_ID = "test_camera"


class NotifierMocks:
    """Typed container for a DiscordNotifier and its patched send methods."""

    def __init__(
        self,
        notifier: DiscordNotifier,
        send_message: MagicMock,
        send_file: MagicMock,
        send_file_partial: MagicMock,
    ) -> None:
        """Initialize the container."""
        self.notifier = notifier
        self.send_message = send_message
        self.send_file = send_file
        self.send_file_partial = send_file_partial


def make_config(
    detection_labels: list[str] | None = None,
    cameras: dict[str, Any] | None = None,
    *,
    send_thumbnail: bool = False,
    send_video: bool = False,
) -> dict:
    """Build a minimal DiscordNotifier config."""
    return {
        CONFIG_DISCORD_WEBHOOK_URL: "https://discord.example.com/webhook",
        CONFIG_DETECTION_LABELS: detection_labels
        if detection_labels is not None
        else DEFAULT_DETECTION_LABELS,
        CONFIG_SEND_THUMBNAIL: send_thumbnail,
        CONFIG_SEND_VIDEO: send_video,
        CONFIG_CAMERAS: cameras if cameras is not None else {CAMERA_ID: {}},
    }


def make_detected_object(label: str) -> DetectedObject:
    """Build a minimal DetectedObject with the given label."""
    return DetectedObject(
        label=label,
        confidence=0.9,
        x1=0.1,
        y1=0.1,
        x2=0.5,
        y2=0.5,
        frame_res=(1920, 1080),
    )


def make_recording(
    objects: list[DetectedObject],
    recording_id: int = 1,
    thumbnail_path: str | None = None,
    clip_path: str | None = None,
) -> Recording:
    """Build a minimal Recording with the given detected objects."""
    return Recording(
        id=recording_id,
        start_time=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
        start_timestamp=0.0,
        end_time=datetime.datetime(2025, 1, 1, 0, 0, 10, tzinfo=datetime.timezone.utc),
        end_timestamp=10.0,
        date="2025-01-01",
        thumbnail=None,
        thumbnail_path=thumbnail_path,
        clip_path=clip_path,
        objects=objects,
        trigger_type=TriggerTypes.OBJECT,
    )


def make_event(recording: Recording) -> Event[EventRecorderData]:
    """Build an Event wrapping the given recording."""
    camera_mock = MagicMock()
    camera_mock.identifier = CAMERA_ID
    event_data = EventRecorderData(camera=camera_mock, recording=recording)
    return Event(name="test", data=event_data, timestamp=0.0)


@pytest.fixture
def notifier(vis: MockViseron):
    """Return a DiscordNotifier with patched send methods."""
    config = make_config()
    with patch("viseron.components.discord.RestartableThread"):
        n = DiscordNotifier(vis, config)
    with (
        patch.object(
            n, "_send_discord_message", MagicMock(return_value=True)
        ) as send_message,
        patch.object(
            n, "_send_discord_file", MagicMock(return_value=True)
        ) as send_file,
        patch.object(
            n, "_send_discord_file_partial", MagicMock(return_value=True)
        ) as send_file_partial,
    ):
        yield NotifierMocks(n, send_message, send_file, send_file_partial)


def run_async_recorder_complete(
    notifier: DiscordNotifier, event: Event[EventRecorderData]
):
    """Run _async_recorder_complete_event synchronously via a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(notifier._async_recorder_complete_event(event))
    finally:
        loop.close()


def run_recorder_start_event(
    notifier: DiscordNotifier, event: Event[EventRecorderData]
) -> None:
    """Run _recorder_start_event synchronously."""
    notifier._recorder_start_event(event)


class TestSetupUnload:
    """Tests for module-level setup and unload functions."""

    def test_setup_stores_notifier_and_returns_true(self, vis: MockViseron):
        """Setup stores a DiscordNotifier instance and returns True."""
        config = {COMPONENT: make_config()}
        with patch("viseron.components.discord.RestartableThread"):
            result = setup(vis, config)

        assert result is True
        assert isinstance(vis.data[COMPONENT], DiscordNotifier)

    def test_unload_stops_notifier_and_removes_key(self, vis: MockViseron):
        """Unload stops the notifier and removes it from vis.data."""
        notifier_mock = MagicMock()
        vis.data[COMPONENT] = notifier_mock

        unload(vis)

        notifier_mock.stop.assert_called_once()
        assert COMPONENT not in vis.data


class TestInitEventRegistration:
    """Tests for DiscordNotifier __init__ event registration."""

    def test_registers_start_and_complete_events_for_each_camera(
        self, vis: MockViseron
    ):
        """One start and one complete event listener is registered per camera."""
        cameras: dict[str, Any] = {"cam_one": {}, "cam_two": {}}
        config = make_config(cameras=cameras)
        with patch("viseron.components.discord.RestartableThread"):
            notifier = DiscordNotifier(vis, config)

        assert vis.listen_event.call_count == 4
        expected_calls = [
            call(EVENT_RECORDER_START.format(camera_identifier="cam_one"), ANY),
            call(EVENT_RECORDER_COMPLETE.format(camera_identifier="cam_one"), ANY),
            call(EVENT_RECORDER_START.format(camera_identifier="cam_two"), ANY),
            call(EVENT_RECORDER_COMPLETE.format(camera_identifier="cam_two"), ANY),
        ]
        vis.listen_event.assert_has_calls(expected_calls, any_order=True)

        vis.register_signal_handler.assert_called_once_with(
            VISERON_SIGNAL_SHUTDOWN, notifier.stop
        )

    def test_starts_background_thread(self, vis: MockViseron):
        """The DiscordNotifier starts its background event-loop thread."""
        with patch("viseron.components.discord.RestartableThread") as mock_thread:
            notifier = DiscordNotifier(vis, make_config())

        mock_thread.assert_called_once_with(
            name="DiscordNotifierThread", daemon=True, target=notifier.run_async
        )
        mock_thread.return_value.start.assert_called_once()


class TestRecorderStartEvent:
    """Tests for _recorder_start_event."""

    @pytest.fixture
    def start_notifier(self, vis: MockViseron):
        """Return a DiscordNotifier configured to send thumbnails."""
        config = make_config(send_thumbnail=True)
        with patch("viseron.components.discord.RestartableThread"):
            n = DiscordNotifier(vis, config)
        with (
            patch.object(
                n, "_send_discord_message", MagicMock(return_value=True)
            ) as send_message,
            patch.object(
                n, "_send_discord_file", MagicMock(return_value=True)
            ) as send_file,
            patch.object(
                n, "_send_discord_file_partial", MagicMock(return_value=True)
            ) as send_file_partial,
        ):
            yield NotifierMocks(n, send_message, send_file, send_file_partial)

    def test_sends_thumbnail_when_file_exists(self, start_notifier: NotifierMocks):
        """Start event sends thumbnail when configured and file exists."""
        recording = make_recording(
            [make_detected_object("person")],
            thumbnail_path="/path/to/thumb.jpg",
        )
        event = make_event(recording)

        with patch("viseron.components.discord.os.path.exists", return_value=True):
            run_recorder_start_event(start_notifier.notifier, event)

        start_notifier.send_file.assert_called_once_with(
            "/path/to/thumb.jpg",
            "Recording started on test_camera - Detected person",
            "thumbnail.jpg",
            CAMERA_ID,
        )
        start_notifier.send_message.assert_not_called()

    def test_sends_message_only_when_thumbnail_disabled(
        self, start_notifier: NotifierMocks
    ):
        """Start event sends only a message when send_thumbnail is False."""
        start_notifier.notifier._config[CONFIG_SEND_THUMBNAIL] = False
        recording = make_recording(
            [make_detected_object("person")],
            thumbnail_path="/path/to/thumb.jpg",
        )
        event = make_event(recording)

        run_recorder_start_event(start_notifier.notifier, event)

        start_notifier.send_message.assert_called_once_with(
            "Recording started on test_camera - Detected person", CAMERA_ID
        )
        start_notifier.send_file.assert_not_called()

    def test_sends_message_only_when_thumbnail_path_is_none(
        self, start_notifier: NotifierMocks
    ):
        """Start event sends only a message when thumbnail_path is None."""
        recording = make_recording([make_detected_object("person")])
        event = make_event(recording)

        run_recorder_start_event(start_notifier.notifier, event)

        start_notifier.send_message.assert_called_once()
        start_notifier.send_file.assert_not_called()

    def test_sends_message_only_when_thumbnail_file_missing(
        self, start_notifier: NotifierMocks
    ):
        """Start event sends only a message when thumbnail file is missing."""
        recording = make_recording(
            [make_detected_object("person")],
            thumbnail_path="/path/to/missing.jpg",
        )
        event = make_event(recording)

        with patch("viseron.components.discord.os.path.exists", return_value=False):
            run_recorder_start_event(start_notifier.notifier, event)

        start_notifier.send_message.assert_called_once()
        start_notifier.send_file.assert_not_called()

    def test_skips_when_label_does_not_match(self, start_notifier: NotifierMocks):
        """Start event sends nothing when detected label does not match."""
        start_notifier.notifier._config[CONFIG_DETECTION_LABELS] = ["person"]
        recording = make_recording([make_detected_object("car")])
        event = make_event(recording)

        run_recorder_start_event(start_notifier.notifier, event)

        start_notifier.send_message.assert_not_called()
        start_notifier.send_file.assert_not_called()

    def test_sends_message_for_manual_recording_with_no_objects(
        self, start_notifier: NotifierMocks
    ):
        """Start event sends message for recordings with no detected objects."""
        recording = make_recording([])
        recording.trigger_type = TriggerTypes.MANUAL
        event = make_event(recording)

        run_recorder_start_event(start_notifier.notifier, event)

        start_notifier.send_message.assert_called_once_with(
            "Recording started on test_camera", CAMERA_ID
        )


class TestDetectionLabelFiltering:
    """Tests for detection_label filtering in Discord."""

    def test_sends_when_label_matches_global(self, notifier: NotifierMocks):
        """Notification sent when detected object matches global detection_labels."""
        recording = make_recording([make_detected_object("person")])
        event = make_event(recording)
        run_async_recorder_complete(notifier.notifier, event)
        notifier.send_message.assert_called_once()

    def test_skips_when_label_does_not_match_global(self, notifier: NotifierMocks):
        """No notification when detected object does not match detection_labels."""
        recording = make_recording([make_detected_object("car")])
        event = make_event(recording)
        notifier.notifier._config[CONFIG_DETECTION_LABELS] = ["person"]
        run_async_recorder_complete(notifier.notifier, event)
        notifier.send_message.assert_not_called()
        notifier.send_file.assert_not_called()

    def test_sends_for_manual_recording_with_no_objects(self, notifier: NotifierMocks):
        """Notification sent when recording has no detected objects (e.g. manual)."""
        recording = make_recording([])
        recording.trigger_type = TriggerTypes.MANUAL
        event = make_event(recording)
        notifier.notifier._config[CONFIG_DETECTION_LABELS] = ["person"]
        run_async_recorder_complete(notifier.notifier, event)
        notifier.send_message.assert_called_once()

    def test_camera_level_overrides_global(self, vis: MockViseron):
        """Camera-level detection_labels overrides the global setting."""
        cameras = {CAMERA_ID: {CONFIG_DETECTION_LABELS: ["car"]}}
        config = make_config(detection_labels=["person"], cameras=cameras)
        with patch("viseron.components.discord.RestartableThread"):
            n = DiscordNotifier(vis, config)
        with (
            patch.object(
                n, "_send_discord_message", MagicMock(return_value=True)
            ) as send_message,
            patch.object(
                n, "_send_discord_file", MagicMock(return_value=True)
            ) as send_file,
        ):
            # "car" matches camera-level override → should send
            recording = make_recording([make_detected_object("car")])
            run_async_recorder_complete(n, make_event(recording))
            send_message.assert_called_once()

            send_message.reset_mock()

            # "person" matches global but NOT camera-level → should NOT send
            recording2 = make_recording([make_detected_object("person")])
            run_async_recorder_complete(n, make_event(recording2))
            send_message.assert_not_called()
            send_file.assert_not_called()

    def test_global_deprecated_comma_separated_label(self, notifier: NotifierMocks):
        """Deprecated comma-separated detection_label still works at global level."""
        recording = make_recording([make_detected_object("cat")])
        event = make_event(recording)
        notifier.notifier._config[CONFIG_DETECTION_LABELS] = None
        notifier.notifier._config[CONFIG_DETECTION_LABEL] = "person,cat"
        run_async_recorder_complete(notifier.notifier, event)
        notifier.send_message.assert_called_once()

    def test_empty_objects_always_matches(self, notifier: NotifierMocks):
        """Recordings with no objects always match the configured labels."""
        matches, label = notifier.notifier._matches_detection_label(CAMERA_ID, [])

        assert matches is True
        assert label is None


class TestRecorderCompleteEventVideoPaths:
    """Tests for _async_recorder_complete_event video/partial/fallback paths."""

    @pytest.fixture
    def video_notifier(self, vis: MockViseron):
        """Return a DiscordNotifier configured to send videos."""
        config = make_config(send_video=True)
        with patch("viseron.components.discord.RestartableThread"):
            n = DiscordNotifier(vis, config)
        with (
            patch.object(
                n, "_send_discord_message", MagicMock(return_value=True)
            ) as send_message,
            patch.object(
                n, "_send_discord_file", MagicMock(return_value=True)
            ) as send_file,
            patch.object(
                n, "_send_discord_file_partial", MagicMock(return_value=True)
            ) as send_file_partial,
        ):
            yield NotifierMocks(n, send_message, send_file, send_file_partial)

    def test_sends_complete_video_when_under_size_limit(
        self, video_notifier: NotifierMocks
    ):
        """Complete video is sent when file size is within the limit."""
        recording = make_recording(
            [make_detected_object("person")],
            clip_path="/path/to/event.mp4",
        )
        event = make_event(recording)

        with (
            patch(
                "viseron.components.discord.aiofiles.os.path.exists", return_value=True
            ),
            patch(
                "viseron.components.discord.aiofiles.os.path.getsize",
                return_value=100,
            ),
        ):
            run_async_recorder_complete(video_notifier.notifier, event)

        video_notifier.send_file.assert_called_once_with(
            "/path/to/event.mp4",
            "Complete video from test_camera - Detected person",
            "test_camera_event_complete.mp4",
            CAMERA_ID,
        )
        video_notifier.send_message.assert_not_called()
        video_notifier.send_file_partial.assert_not_called()

    def test_sends_partial_video_when_over_size_limit(
        self, video_notifier: NotifierMocks
    ):
        """Partial video is sent when file size exceeds the limit."""
        recording = make_recording(
            [make_detected_object("person")],
            clip_path="/path/to/event.mp4",
        )
        event = make_event(recording)
        file_size = 10 * 1024 * 1024
        max_size_bytes = 8 * 1024 * 1024

        with (
            patch(
                "viseron.components.discord.aiofiles.os.path.exists", return_value=True
            ),
            patch(
                "viseron.components.discord.aiofiles.os.path.getsize",
                return_value=file_size,
            ),
        ):
            run_async_recorder_complete(video_notifier.notifier, event)

        video_notifier.send_file_partial.assert_called_once_with(
            "/path/to/event.mp4",
            (
                "Complete video from test_camera - Detected person \r\n"
                "Truncated to 8MB / 80% of the original video due to Discord file "
                "size limit.\r\n"
                "Note: The video player may show the full duration, but playback "
                "will stop early due to truncation."
            ),
            "test_camera_event_partial.mp4",
            max_size_bytes,
            CAMERA_ID,
        )
        video_notifier.send_file.assert_not_called()
        video_notifier.send_message.assert_not_called()

    def test_fallback_to_message_and_thumbnail_when_video_disabled(
        self, video_notifier: NotifierMocks
    ):
        """Message and thumbnail are sent when video sending is disabled."""
        video_notifier.notifier._config[CONFIG_SEND_VIDEO] = False
        video_notifier.notifier._config[CONFIG_SEND_THUMBNAIL] = True
        recording = make_recording(
            [make_detected_object("person")],
            thumbnail_path="/path/to/thumb.jpg",
        )
        event = make_event(recording)

        with patch(
            "viseron.components.discord.aiofiles.os.path.exists", return_value=True
        ):
            run_async_recorder_complete(video_notifier.notifier, event)

        video_notifier.send_message.assert_called_once_with(
            "Recording completed for test_camera - Detected person", CAMERA_ID
        )
        video_notifier.send_file.assert_called_once_with(
            "/path/to/thumb.jpg",
            "Thumbnail for test_camera",
            "thumbnail.jpg",
            CAMERA_ID,
        )

    def test_message_only_fallback_when_video_and_thumbnail_unavailable(
        self, video_notifier: NotifierMocks
    ):
        """Only a message is sent when neither video nor thumbnail can be sent."""
        video_notifier.notifier._config[CONFIG_SEND_VIDEO] = False
        video_notifier.notifier._config[CONFIG_SEND_THUMBNAIL] = False
        recording = make_recording([make_detected_object("person")])
        event = make_event(recording)

        run_async_recorder_complete(video_notifier.notifier, event)

        video_notifier.send_message.assert_called_once_with(
            "Recording completed for test_camera - Detected person", CAMERA_ID
        )
        video_notifier.send_file.assert_not_called()

    def test_fallback_when_clip_path_is_none(self, video_notifier: NotifierMocks):
        """Fallback path is taken when the recording has no clip_path."""
        video_notifier.notifier._config[CONFIG_SEND_THUMBNAIL] = True
        recording = make_recording(
            [make_detected_object("person")],
            thumbnail_path="/path/to/thumb.jpg",
        )
        event = make_event(recording)

        with patch(
            "viseron.components.discord.aiofiles.os.path.exists", return_value=True
        ):
            run_async_recorder_complete(video_notifier.notifier, event)

        video_notifier.send_message.assert_called_once()
        video_notifier.send_file.assert_called_once_with(
            "/path/to/thumb.jpg",
            "Thumbnail for test_camera",
            "thumbnail.jpg",
            CAMERA_ID,
        )
        video_notifier.send_file_partial.assert_not_called()

    def test_skips_when_label_does_not_match(self, video_notifier: NotifierMocks):
        """Complete event sends nothing when detected label does not match."""
        video_notifier.notifier._config[CONFIG_DETECTION_LABELS] = ["person"]
        recording = make_recording([make_detected_object("car")])
        event = make_event(recording)

        run_async_recorder_complete(video_notifier.notifier, event)

        video_notifier.send_message.assert_not_called()
        video_notifier.send_file.assert_not_called()
        video_notifier.send_file_partial.assert_not_called()

    def test_complete_event_wrapper_schedules_async_handler(
        self, notifier: NotifierMocks
    ):
        """_recorder_complete_event schedules the async handler on the event loop."""
        recording = make_recording([make_detected_object("person")])
        event = make_event(recording)
        fake_coro = MagicMock()
        fake_async_method = MagicMock(return_value=fake_coro)

        with (
            patch(
                "viseron.components.discord.asyncio.run_coroutine_threadsafe"
            ) as mock_run,
            patch.object(
                notifier.notifier,
                "_async_recorder_complete_event",
                new=fake_async_method,
            ),
        ):
            notifier.notifier._recorder_complete_event(event)

        fake_async_method.assert_called_once_with(event)
        mock_run.assert_called_once_with(fake_coro, notifier.notifier._loop)


class TestSendDiscordMessage:
    """Tests for _send_discord_message."""

    @pytest.fixture
    def http_notifier(self, vis: MockViseron) -> DiscordNotifier:
        """Return a DiscordNotifier with real HTTP send methods."""
        with patch("viseron.components.discord.RestartableThread"):
            return DiscordNotifier(vis, make_config())

    def test_success_sends_json_payload(self, http_notifier: DiscordNotifier):
        """_send_discord_message posts JSON content and returns True."""
        with patch("viseron.components.discord.requests.post") as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            result = http_notifier._send_discord_message("Hello", CAMERA_ID)

        assert result is True
        mock_post.assert_called_once_with(
            "https://discord.example.com/webhook",
            json={"content": "Hello"},
            timeout=30,
        )

    def test_failure_returns_false(self, http_notifier: DiscordNotifier):
        """_send_discord_message returns False when the request fails."""
        with patch(
            "viseron.components.discord.requests.post",
            side_effect=requests.RequestException("boom"),
        ) as mock_post:
            result = http_notifier._send_discord_message("Hello", CAMERA_ID)

        assert result is False
        mock_post.assert_called_once()

    def test_uses_camera_specific_webhook_url(self, vis: MockViseron):
        """Camera-level webhook_url overrides the global URL."""
        camera_url = "https://discord.camera.example.com/webhook"
        config = make_config(
            cameras={CAMERA_ID: {CONFIG_DISCORD_WEBHOOK_URL: camera_url}}
        )
        with patch("viseron.components.discord.RestartableThread"):
            notifier = DiscordNotifier(vis, config)

        with patch("viseron.components.discord.requests.post") as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            notifier._send_discord_message("Hello", CAMERA_ID)

        mock_post.assert_called_once_with(
            camera_url,
            json={"content": "Hello"},
            timeout=30,
        )


class TestSendDiscordFile:
    """Tests for _send_discord_file."""

    @pytest.fixture
    def http_notifier(self, vis: MockViseron) -> DiscordNotifier:
        """Return a DiscordNotifier with real HTTP send methods."""
        with patch("viseron.components.discord.RestartableThread"):
            return DiscordNotifier(vis, make_config())

    def test_success_posts_file_and_content(self, http_notifier: DiscordNotifier):
        """_send_discord_file posts the file and content, returning True."""
        with patch("viseron.components.discord.requests.post") as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            with patch(
                "viseron.components.discord.open",
                mock_open(read_data=b"fake file data"),
            ) as mock_file:
                result = http_notifier._send_discord_file(
                    "/path/to/file.mp4", "caption", "video.mp4", CAMERA_ID
                )

        assert result is True
        mock_file.assert_called_once_with("/path/to/file.mp4", "rb")
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args.kwargs["data"] == {"content": "caption"}
        assert call_args.kwargs["timeout"] == 60

    def test_failure_returns_false(self, http_notifier: DiscordNotifier):
        """_send_discord_file returns False when the request fails."""
        with (
            patch(
                "viseron.components.discord.requests.post",
                side_effect=requests.RequestException("boom"),
            ) as mock_post,
            patch("viseron.components.discord.open", mock_open(read_data=b"")),
        ):
            result = http_notifier._send_discord_file(
                "/path/to/file.mp4", "caption", "video.mp4", CAMERA_ID
            )

        assert result is False
        mock_post.assert_called_once()

    def test_uses_camera_specific_webhook_url(self, vis: MockViseron):
        """Camera-level webhook_url overrides the global URL for file sends."""
        camera_url = "https://discord.camera.example.com/webhook"
        config = make_config(
            cameras={CAMERA_ID: {CONFIG_DISCORD_WEBHOOK_URL: camera_url}}
        )
        with patch("viseron.components.discord.RestartableThread"):
            notifier = DiscordNotifier(vis, config)

        with patch("viseron.components.discord.requests.post") as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            with patch("viseron.components.discord.open", mock_open(read_data=b"")):
                notifier._send_discord_file(
                    "/path/to/file.mp4", "caption", "video.mp4", CAMERA_ID
                )

        mock_post.assert_called_once()
        assert mock_post.call_args.args[0] == camera_url


class TestSendDiscordFilePartial:
    """Tests for _send_discord_file_partial."""

    @pytest.fixture
    def http_notifier(self, vis: MockViseron) -> DiscordNotifier:
        """Return a DiscordNotifier with real HTTP send methods."""
        with patch("viseron.components.discord.RestartableThread"):
            return DiscordNotifier(vis, make_config())

    def test_success_reads_only_max_bytes(self, http_notifier: DiscordNotifier):
        """_send_discord_file_partial reads only max_bytes and returns True."""
        max_bytes = 1024
        data = b"x" * (max_bytes + 100)

        with patch("viseron.components.discord.requests.post") as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            with patch(
                "viseron.components.discord.open", mock_open(read_data=data)
            ) as mock_file:
                result = http_notifier._send_discord_file_partial(
                    "/path/to/file.mp4", "caption", "video.mp4", max_bytes, CAMERA_ID
                )

        assert result is True
        mock_file.assert_called_once_with("/path/to/file.mp4", "rb")
        sent_file = mock_post.call_args.kwargs["files"]["file"]
        assert sent_file[1] == data[:max_bytes]
        assert len(sent_file[1]) == max_bytes

    def test_failure_returns_false(self, http_notifier: DiscordNotifier):
        """_send_discord_file_partial returns False when the request fails."""
        with (
            patch(
                "viseron.components.discord.requests.post",
                side_effect=requests.RequestException("boom"),
            ) as mock_post,
            patch("viseron.components.discord.open", mock_open(read_data=b"data")),
        ):
            result = http_notifier._send_discord_file_partial(
                "/path/to/file.mp4", "caption", "video.mp4", 4, CAMERA_ID
            )

        assert result is False
        mock_post.assert_called_once()


class TestGetEffectiveDetectionLabels:
    """Tests for _get_effective_detection_labels."""

    def test_undefined_camera_labels_falls_through_to_global(self, vis: MockViseron):
        """UNDEFINED camera detection_labels falls through to global labels."""
        cameras = {CAMERA_ID: {CONFIG_DETECTION_LABELS: UNDEFINED}}
        config = make_config(detection_labels=["car"], cameras=cameras)
        with patch("viseron.components.discord.RestartableThread"):
            notifier = DiscordNotifier(vis, config)

        labels = notifier._get_effective_detection_labels(CAMERA_ID)

        assert labels == ["car"]

    def test_undefined_camera_labels_does_not_raise_on_notification(
        self, vis: MockViseron
    ):
        """Detection with UNDEFINED camera labels does not raise TypeError."""
        cameras = {CAMERA_ID: {CONFIG_DETECTION_LABELS: UNDEFINED}}
        config = make_config(detection_labels=["person"], cameras=cameras)
        with patch("viseron.components.discord.RestartableThread"):
            n = DiscordNotifier(vis, config)
        with (
            patch.object(
                n, "_send_discord_message", MagicMock(return_value=True)
            ) as send_message,
            patch.object(n, "_send_discord_file", MagicMock(return_value=True)),
        ):
            recording = make_recording([make_detected_object("person")])
            run_async_recorder_complete(n, make_event(recording))

            send_message.assert_called_once()

    def test_global_comma_deprecated_label_strips_empty_entries(
        self, notifier: NotifierMocks
    ):
        """Global deprecated detection_label strips empty comma-separated entries."""
        notifier.notifier._config[CONFIG_DETECTION_LABELS] = None
        notifier.notifier._config[CONFIG_DETECTION_LABEL] = ",person,"

        labels = notifier.notifier._get_effective_detection_labels(CAMERA_ID)

        assert "" not in labels
        assert labels == ["person"]

    def test_camera_comma_deprecated_label_strips_empty_entries(self, vis: MockViseron):
        """Camera deprecated detection_label strips empty comma-separated entries."""
        cameras = {CAMERA_ID: {CONFIG_DETECTION_LABEL: ",car,"}}
        config = make_config(cameras=cameras)
        with patch("viseron.components.discord.RestartableThread"):
            notifier = DiscordNotifier(vis, config)

        labels = notifier._get_effective_detection_labels(CAMERA_ID)

        assert "" not in labels
        assert labels == ["car"]

    def test_returns_default_when_no_labels_configured(self, vis: MockViseron):
        """Default detection labels are returned when no labels are configured."""
        config = make_config()
        config[CONFIG_DETECTION_LABEL] = None
        config[CONFIG_DETECTION_LABELS] = []
        config[CONFIG_CAMERAS] = {CAMERA_ID: {}}
        with patch("viseron.components.discord.RestartableThread"):
            notifier = DiscordNotifier(vis, config)

        labels = notifier._get_effective_detection_labels(CAMERA_ID)

        assert labels == DEFAULT_DETECTION_LABELS


class TestGetCameraConfig:
    """Tests for _get_camera_config."""

    def test_returns_camera_specific_value(self, vis: MockViseron):
        """Camera-specific config key takes precedence."""
        cameras = {CAMERA_ID: {CONFIG_MAX_VIDEO_SIZE_MB: 25}}
        config = make_config(cameras=cameras)
        with patch("viseron.components.discord.RestartableThread"):
            notifier = DiscordNotifier(vis, config)

        value = notifier._get_camera_config(CAMERA_ID, CONFIG_MAX_VIDEO_SIZE_MB)

        assert value == 25

    def test_falls_back_to_global_value(self, vis: MockViseron):
        """Global config is used when camera-specific key is absent."""
        config = make_config()
        config[CONFIG_MAX_VIDEO_SIZE_MB] = 50
        with patch("viseron.components.discord.RestartableThread"):
            notifier = DiscordNotifier(vis, config)

        value = notifier._get_camera_config(CAMERA_ID, CONFIG_MAX_VIDEO_SIZE_MB)

        assert value == 50

    def test_returns_default_when_key_missing_everywhere(self, vis: MockViseron):
        """Default is returned when key is absent at both levels."""
        with patch("viseron.components.discord.RestartableThread"):
            notifier = DiscordNotifier(vis, make_config())

        value = notifier._get_camera_config(
            CAMERA_ID, CONFIG_MAX_VIDEO_SIZE_MB, CONFIG_MAX_VIDEO_SIZE_MB_DEFAULT
        )

        assert value == CONFIG_MAX_VIDEO_SIZE_MB_DEFAULT


class TestGetWebhookUrl:
    """Tests for _get_webhook_url."""

    def test_returns_camera_specific_url(self, vis: MockViseron):
        """Camera-level webhook_url overrides the global webhook URL."""
        camera_url = "https://discord.camera.example.com/webhook"
        config = make_config(
            cameras={CAMERA_ID: {CONFIG_DISCORD_WEBHOOK_URL: camera_url}}
        )
        with patch("viseron.components.discord.RestartableThread"):
            notifier = DiscordNotifier(vis, config)

        url = notifier._get_webhook_url(CAMERA_ID)

        assert url == camera_url

    def test_falls_back_to_global_url(self, vis: MockViseron):
        """Global webhook URL is used when camera-level is absent."""
        with patch("viseron.components.discord.RestartableThread"):
            notifier = DiscordNotifier(vis, make_config())

        url = notifier._get_webhook_url(CAMERA_ID)

        assert url == "https://discord.example.com/webhook"


class TestConfigSchema:
    """Tests for CONFIG_SCHEMA validation."""

    def test_accepts_valid_config(self):
        """CONFIG_SCHEMA accepts a minimally valid config."""
        config = {COMPONENT: make_config()}

        result = CONFIG_SCHEMA(config)

        assert result[COMPONENT][CONFIG_DISCORD_WEBHOOK_URL]
        assert result[COMPONENT][CONFIG_CAMERAS]

    def test_rejects_missing_webhook_url(self):
        """CONFIG_SCHEMA rejects config without webhook_url."""
        config = {COMPONENT: make_config()}
        del config[COMPONENT][CONFIG_DISCORD_WEBHOOK_URL]

        with pytest.raises(vol.error.MultipleInvalid) as exc_info:
            CONFIG_SCHEMA(config)

        assert CONFIG_DISCORD_WEBHOOK_URL in str(exc_info.value)

    def test_rejects_missing_cameras(self):
        """CONFIG_SCHEMA rejects config without cameras."""
        config = {COMPONENT: make_config()}
        del config[COMPONENT][CONFIG_CAMERAS]

        with pytest.raises(vol.error.MultipleInvalid) as exc_info:
            CONFIG_SCHEMA(config)

        assert CONFIG_CAMERAS in str(exc_info.value)

    def test_applies_defaults(self):
        """CONFIG_SCHEMA applies default values for optional keys."""
        config = {
            COMPONENT: {
                CONFIG_DISCORD_WEBHOOK_URL: "https://discord.example.com/webhook",
                CONFIG_CAMERAS: {CAMERA_ID: {}},
            }
        }

        result = CONFIG_SCHEMA(config)

        component_config = result[COMPONENT]
        assert component_config[CONFIG_SEND_THUMBNAIL] is True
        assert component_config[CONFIG_SEND_VIDEO] is True
        assert (
            component_config[CONFIG_MAX_VIDEO_SIZE_MB]
            == CONFIG_MAX_VIDEO_SIZE_MB_DEFAULT
        )
        assert component_config[CONFIG_DETECTION_LABELS] == DEFAULT_DETECTION_LABELS


class TestStop:
    """Tests for DiscordNotifier.stop."""

    def test_unsubscribes_listeners_and_stops_thread(self, vis: MockViseron):
        """Stop unsubscribes event listeners and stops the background thread."""
        with patch("viseron.components.discord.RestartableThread") as mock_thread:
            notifier = DiscordNotifier(vis, make_config())

        listener_mocks = notifier._event_listeners
        assert len(listener_mocks) == 3

        notifier.stop()

        for listener in listener_mocks:
            cast("MagicMock", listener).assert_called_once()
        mock_thread.return_value.stop.assert_called_once()
        mock_thread.return_value.join.assert_called_once()


class TestDeduplication:
    """Tests for recording deduplication."""

    def test_does_not_resend_video_for_same_recording_id(self, vis: MockViseron):
        """Second complete event for same recording id does not resend video."""
        config = make_config(send_video=True)
        with patch("viseron.components.discord.RestartableThread"):
            n = DiscordNotifier(vis, config)
        with (
            patch.object(
                n, "_send_discord_message", MagicMock(return_value=True)
            ) as send_message,
            patch.object(
                n, "_send_discord_file", MagicMock(return_value=True)
            ) as send_file,
            patch.object(
                n, "_send_discord_file_partial", MagicMock(return_value=True)
            ) as send_file_partial,
        ):
            recording = make_recording(
                [make_detected_object("person")], clip_path="/path/to/fake.mp4"
            )
            event = make_event(recording)

            with (
                patch(
                    "viseron.components.discord.aiofiles.os.path.exists",
                    return_value=True,
                ),
                patch(
                    "viseron.components.discord.aiofiles.os.path.getsize",
                    return_value=100,
                ),
            ):
                # First call sends the complete video
                run_async_recorder_complete(n, event)
                send_file.assert_called_once()

                # Reset mocks to verify second call behavior
                send_file.reset_mock()
                send_message.reset_mock()

                # Second call for the same recording id should not resend video
                run_async_recorder_complete(n, event)
                send_file.assert_not_called()
                send_file_partial.assert_not_called()
                send_message.assert_called_once()
