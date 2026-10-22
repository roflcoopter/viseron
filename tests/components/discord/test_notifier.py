"""Tests for the discord component."""

from __future__ import annotations

import asyncio
import datetime
from contextlib import ExitStack
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import ANY, MagicMock, call, mock_open, patch

import pytest
import requests

from viseron.components.discord import CONFIG_SCHEMA, DiscordNotifier, setup, unload
from viseron.components.discord.const import COMPONENT
from viseron.components.storage.models import TriggerTypes
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera.const import EVENT_RECORDER_COMPLETE, EVENT_RECORDER_START
from viseron.domains.camera.recorder import EventRecorderData, Recording
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.events import Event
from viseron.helpers.config_validation import validate_config

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from tests.conftest import MockViseron

    SetUp = Callable[..., DiscordNotifier]
    SetUpMocked = Callable[..., "NotifierMocks"]

CAMERA_ID = "test_camera"
WEBHOOK_URL = "https://discord.example.com/webhook"
CAMERA_WEBHOOK_URL = "https://discord.camera.example.com/webhook"


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


def make_config(**keys: Any) -> dict[str, Any]:
    """Return a config with discord set up with the given keys.

    Thumbnails and videos are off unless the keys turn them on.
    """
    return {
        COMPONENT: {
            "webhook_url": WEBHOOK_URL,
            "send_detection_thumbnail": False,
            "send_detection_video": False,
            "cameras": {CAMERA_ID: None},
            **keys,
        }
    }


@pytest.fixture(name="thread")
def fixture_thread() -> Iterator[MagicMock]:
    """Patch the thread of the notifier."""
    with patch("viseron.components.discord.RestartableThread") as thread:
        yield thread


@pytest.fixture(name="set_up")
def fixture_set_up(
    vis: MockViseron,
    thread: MagicMock,  # noqa: ARG001  # pylint: disable=unused-argument
) -> Iterator[SetUp]:
    """Return a function that sets up discord with the given keys."""
    notifiers: list[DiscordNotifier] = []

    def _set_up(**keys: Any) -> DiscordNotifier:
        assert setup(vis, validate_config(CONFIG_SCHEMA, make_config(**keys)))
        notifiers.append(vis.data[COMPONENT])
        return vis.data[COMPONENT]

    yield _set_up
    for notifier in notifiers:
        notifier._loop.close()


@pytest.fixture(name="set_up_mocked")
def fixture_set_up_mocked(set_up: SetUp) -> Iterator[SetUpMocked]:
    """Return a function that sets up discord with the given keys and mocked sends."""
    with ExitStack() as stack:

        def _set_up_mocked(**keys: Any) -> NotifierMocks:
            notifier = set_up(**keys)

            def mock_send(method: str) -> MagicMock:
                return stack.enter_context(
                    patch.object(notifier, method, MagicMock(return_value=True))
                )

            return NotifierMocks(
                notifier,
                mock_send("_send_discord_message"),
                mock_send("_send_discord_file"),
                mock_send("_send_discord_file_partial"),
            )

        yield _set_up_mocked


@pytest.fixture(name="notifier")
def fixture_notifier(set_up_mocked: SetUpMocked) -> NotifierMocks:
    """Return a DiscordNotifier with patched send methods."""
    return set_up_mocked()


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

    def test_setup_stores_notifier(self, set_up: SetUp, vis: MockViseron):
        """Setup stores a DiscordNotifier instance."""
        set_up()

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
        self, set_up: SetUp, vis: MockViseron
    ):
        """One start and one complete event listener is registered per camera."""
        notifier = set_up(cameras={"cam_one": None, "cam_two": None})

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

    def test_starts_background_thread(self, set_up: SetUp, thread: MagicMock):
        """The DiscordNotifier starts its background event-loop thread."""
        notifier = set_up()

        thread.assert_called_once_with(
            name="DiscordNotifierThread", daemon=True, target=notifier.run_async
        )
        thread.return_value.start.assert_called_once()


class TestRecorderStartEvent:
    """Tests for _recorder_start_event."""

    @pytest.fixture
    def start_notifier(self, set_up_mocked: SetUpMocked) -> NotifierMocks:
        """Return a DiscordNotifier configured to send thumbnails."""
        return set_up_mocked(send_detection_thumbnail=True)

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
        self, set_up_mocked: SetUpMocked
    ):
        """Start event sends only a message when send_thumbnail is False."""
        mocks = set_up_mocked(send_detection_thumbnail=False)
        recording = make_recording(
            [make_detected_object("person")],
            thumbnail_path="/path/to/thumb.jpg",
        )
        event = make_event(recording)

        with patch("viseron.components.discord.os.path.exists", return_value=True):
            run_recorder_start_event(mocks.notifier, event)

        mocks.send_message.assert_called_once_with(
            "Recording started on test_camera - Detected person", CAMERA_ID
        )
        mocks.send_file.assert_not_called()

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
        run_async_recorder_complete(notifier.notifier, event)
        notifier.send_message.assert_not_called()
        notifier.send_file.assert_not_called()

    def test_sends_for_manual_recording_with_no_objects(self, notifier: NotifierMocks):
        """Notification sent when recording has no detected objects (e.g. manual)."""
        recording = make_recording([])
        recording.trigger_type = TriggerTypes.MANUAL
        event = make_event(recording)
        run_async_recorder_complete(notifier.notifier, event)
        notifier.send_message.assert_called_once()

    def test_camera_level_overrides_global(self, set_up_mocked: SetUpMocked):
        """Camera-level detection_labels overrides the global setting."""
        mocks = set_up_mocked(
            detection_labels=["person"],
            cameras={CAMERA_ID: {"detection_labels": ["car"]}},
        )

        # "car" matches camera-level override → should send
        recording = make_recording([make_detected_object("car")])
        run_async_recorder_complete(mocks.notifier, make_event(recording))
        mocks.send_message.assert_called_once()

        mocks.send_message.reset_mock()

        # "person" matches global but NOT camera-level → should NOT send
        recording2 = make_recording([make_detected_object("person")])
        run_async_recorder_complete(mocks.notifier, make_event(recording2))
        mocks.send_message.assert_not_called()
        mocks.send_file.assert_not_called()

    def test_global_deprecated_comma_separated_label(self, set_up_mocked: SetUpMocked):
        """Deprecated comma-separated detection_label still works at global level."""
        mocks = set_up_mocked(detection_label="person,cat")
        recording = make_recording([make_detected_object("cat")])
        event = make_event(recording)
        run_async_recorder_complete(mocks.notifier, event)
        mocks.send_message.assert_called_once()

    def test_empty_objects_always_matches(self, notifier: NotifierMocks):
        """Recordings with no objects always match the configured labels."""
        matches, label = notifier.notifier._matches_detection_label(CAMERA_ID, [])

        assert matches is True
        assert label is None


class TestRecorderCompleteEventVideoPaths:
    """Tests for _async_recorder_complete_event video/partial/fallback paths."""

    @pytest.fixture
    def video_notifier(self, set_up_mocked: SetUpMocked) -> NotifierMocks:
        """Return a DiscordNotifier configured to send videos."""
        return set_up_mocked(send_detection_video=True)

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
        self, set_up_mocked: SetUpMocked
    ):
        """Message and thumbnail are sent when video sending is disabled."""
        mocks = set_up_mocked(send_detection_thumbnail=True)
        recording = make_recording(
            [make_detected_object("person")],
            thumbnail_path="/path/to/thumb.jpg",
        )
        event = make_event(recording)

        with patch(
            "viseron.components.discord.aiofiles.os.path.exists", return_value=True
        ):
            run_async_recorder_complete(mocks.notifier, event)

        mocks.send_message.assert_called_once_with(
            "Recording completed for test_camera - Detected person", CAMERA_ID
        )
        mocks.send_file.assert_called_once_with(
            "/path/to/thumb.jpg",
            "Thumbnail for test_camera",
            "thumbnail.jpg",
            CAMERA_ID,
        )

    def test_message_only_fallback_when_video_and_thumbnail_unavailable(
        self, notifier: NotifierMocks
    ):
        """Only a message is sent when neither video nor thumbnail can be sent."""
        recording = make_recording([make_detected_object("person")])
        event = make_event(recording)

        run_async_recorder_complete(notifier.notifier, event)

        notifier.send_message.assert_called_once_with(
            "Recording completed for test_camera - Detected person", CAMERA_ID
        )
        notifier.send_file.assert_not_called()

    def test_fallback_when_clip_path_is_none(self, set_up_mocked: SetUpMocked):
        """Fallback path is taken when the recording has no clip_path."""
        mocks = set_up_mocked(send_detection_video=True, send_detection_thumbnail=True)
        recording = make_recording(
            [make_detected_object("person")],
            thumbnail_path="/path/to/thumb.jpg",
        )
        event = make_event(recording)

        with patch(
            "viseron.components.discord.aiofiles.os.path.exists", return_value=True
        ):
            run_async_recorder_complete(mocks.notifier, event)

        mocks.send_message.assert_called_once()
        mocks.send_file.assert_called_once_with(
            "/path/to/thumb.jpg",
            "Thumbnail for test_camera",
            "thumbnail.jpg",
            CAMERA_ID,
        )
        mocks.send_file_partial.assert_not_called()

    def test_skips_when_label_does_not_match(self, video_notifier: NotifierMocks):
        """Complete event sends nothing when detected label does not match."""
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


class TestCameraOverrides:
    """Tests for camera keys that override the global ones."""

    @pytest.mark.usefixtures("thread")
    def test_thumbnail_and_video_are_sent_by_default(self, vis: MockViseron):
        """Without the keys, thumbnails and videos are sent."""
        config = {COMPONENT: {"webhook_url": WEBHOOK_URL, "cameras": {CAMERA_ID: None}}}
        setup(vis, validate_config(CONFIG_SCHEMA, config))
        notifier: DiscordNotifier = vis.data[COMPONENT]
        recording = make_recording(
            [make_detected_object("person")],
            thumbnail_path="/path/to/thumb.jpg",
            clip_path="/path/to/event.mp4",
        )

        with (
            patch.object(notifier, "_send_discord_file") as send_file,
            patch("viseron.components.discord.os.path.exists", return_value=True),
            patch(
                "viseron.components.discord.aiofiles.os.path.exists", return_value=True
            ),
            patch(
                "viseron.components.discord.aiofiles.os.path.getsize",
                return_value=100,
            ),
        ):
            run_recorder_start_event(notifier, make_event(recording))
            run_async_recorder_complete(notifier, make_event(recording))
        notifier._loop.close()

        assert [args[0] for args, _ in send_file.call_args_list] == [
            "/path/to/thumb.jpg",
            "/path/to/event.mp4",
        ]

    def test_camera_send_thumbnail_overrides_global(self, set_up_mocked: SetUpMocked):
        """The camera's send_detection_thumbnail wins over the global one."""
        mocks = set_up_mocked(
            send_detection_thumbnail=False,
            cameras={CAMERA_ID: {"send_detection_thumbnail": True}},
        )
        recording = make_recording(
            [make_detected_object("person")], thumbnail_path="/path/to/thumb.jpg"
        )

        with patch("viseron.components.discord.os.path.exists", return_value=True):
            run_recorder_start_event(mocks.notifier, make_event(recording))

        mocks.send_file.assert_called_once()
        mocks.send_message.assert_not_called()

    def test_camera_send_video_overrides_global(self, set_up_mocked: SetUpMocked):
        """The camera's send_detection_video wins over the global one."""
        mocks = set_up_mocked(
            send_detection_video=True,
            cameras={CAMERA_ID: {"send_detection_video": False}},
        )
        recording = make_recording(
            [make_detected_object("person")], clip_path="/path/to/event.mp4"
        )

        with patch(
            "viseron.components.discord.aiofiles.os.path.exists", return_value=True
        ):
            run_async_recorder_complete(mocks.notifier, make_event(recording))

        mocks.send_message.assert_called_once()
        mocks.send_file.assert_not_called()
        mocks.send_file_partial.assert_not_called()

    @pytest.mark.parametrize(
        ("keys", "file_size_mb", "partial_max_mb"),
        [
            pytest.param({"max_video_size_mb": 50}, 10, None, id="global"),
            pytest.param(
                {
                    "max_video_size_mb": 50,
                    "cameras": {CAMERA_ID: {"max_video_size_mb": 1}},
                },
                2,
                1,
                id="camera",
            ),
        ],
    )
    def test_max_video_size(
        self,
        set_up_mocked: SetUpMocked,
        keys: dict[str, Any],
        file_size_mb: int,
        partial_max_mb: int | None,
    ):
        """The camera's max_video_size_mb wins over the global one."""
        mocks = set_up_mocked(send_detection_video=True, **keys)
        recording = make_recording(
            [make_detected_object("person")], clip_path="/path/to/event.mp4"
        )

        with (
            patch(
                "viseron.components.discord.aiofiles.os.path.exists", return_value=True
            ),
            patch(
                "viseron.components.discord.aiofiles.os.path.getsize",
                return_value=file_size_mb * 1024 * 1024,
            ),
        ):
            run_async_recorder_complete(mocks.notifier, make_event(recording))

        if partial_max_mb is None:
            mocks.send_file.assert_called_once()
            mocks.send_file_partial.assert_not_called()
        else:
            mocks.send_file.assert_not_called()
            assert (
                mocks.send_file_partial.call_args.args[3]
                == partial_max_mb * 1024 * 1024
            )


class TestSendDiscordMessage:
    """Tests for _send_discord_message."""

    def test_success_sends_json_payload(self, set_up: SetUp):
        """_send_discord_message posts JSON content and returns True."""
        http_notifier = set_up()
        with patch("viseron.components.discord.requests.post") as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            result = http_notifier._send_discord_message("Hello", CAMERA_ID)

        assert result is True
        mock_post.assert_called_once_with(
            WEBHOOK_URL,
            json={"content": "Hello"},
            timeout=30,
        )

    def test_failure_returns_false(self, set_up: SetUp):
        """_send_discord_message returns False when the request fails."""
        http_notifier = set_up()
        with patch(
            "viseron.components.discord.requests.post",
            side_effect=requests.RequestException("boom"),
        ) as mock_post:
            result = http_notifier._send_discord_message("Hello", CAMERA_ID)

        assert result is False
        mock_post.assert_called_once()

    def test_uses_camera_specific_webhook_url(self, set_up: SetUp):
        """Camera-level webhook_url overrides the global URL."""
        notifier = set_up(cameras={CAMERA_ID: {"webhook_url": CAMERA_WEBHOOK_URL}})

        with patch("viseron.components.discord.requests.post") as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            notifier._send_discord_message("Hello", CAMERA_ID)

        mock_post.assert_called_once_with(
            CAMERA_WEBHOOK_URL,
            json={"content": "Hello"},
            timeout=30,
        )


class TestSendDiscordFile:
    """Tests for _send_discord_file."""

    def test_success_posts_file_and_content(self, set_up: SetUp):
        """_send_discord_file posts the file and content, returning True."""
        http_notifier = set_up()
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
        assert call_args.args[0] == WEBHOOK_URL
        assert call_args.kwargs["data"] == {"content": "caption"}
        assert call_args.kwargs["timeout"] == 60

    def test_failure_returns_false(self, set_up: SetUp):
        """_send_discord_file returns False when the request fails."""
        http_notifier = set_up()
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

    def test_uses_camera_specific_webhook_url(self, set_up: SetUp):
        """Camera-level webhook_url overrides the global URL for file sends."""
        notifier = set_up(cameras={CAMERA_ID: {"webhook_url": CAMERA_WEBHOOK_URL}})

        with patch("viseron.components.discord.requests.post") as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            with patch("viseron.components.discord.open", mock_open(read_data=b"")):
                notifier._send_discord_file(
                    "/path/to/file.mp4", "caption", "video.mp4", CAMERA_ID
                )

        mock_post.assert_called_once()
        assert mock_post.call_args.args[0] == CAMERA_WEBHOOK_URL


class TestSendDiscordFilePartial:
    """Tests for _send_discord_file_partial."""

    def test_success_reads_only_max_bytes(self, set_up: SetUp):
        """_send_discord_file_partial reads only max_bytes and returns True."""
        http_notifier = set_up()
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
        assert mock_post.call_args.args[0] == WEBHOOK_URL
        sent_file = mock_post.call_args.kwargs["files"]["file"]
        assert sent_file[1] == data[:max_bytes]
        assert len(sent_file[1]) == max_bytes

    def test_failure_returns_false(self, set_up: SetUp):
        """_send_discord_file_partial returns False when the request fails."""
        http_notifier = set_up()
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

    def test_uses_camera_specific_webhook_url(self, set_up: SetUp):
        """Camera-level webhook_url overrides the global URL for partial sends."""
        notifier = set_up(cameras={CAMERA_ID: {"webhook_url": CAMERA_WEBHOOK_URL}})

        with patch("viseron.components.discord.requests.post") as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            with patch("viseron.components.discord.open", mock_open(read_data=b"")):
                notifier._send_discord_file_partial(
                    "/path/to/file.mp4", "caption", "video.mp4", 4, CAMERA_ID
                )

        mock_post.assert_called_once()
        assert mock_post.call_args.args[0] == CAMERA_WEBHOOK_URL


@pytest.mark.filterwarnings("error::DeprecationWarning")
class TestGetEffectiveDetectionLabels:
    """Tests for _get_effective_detection_labels."""

    def test_unset_camera_labels_fall_through_to_global(self, set_up: SetUp):
        """Camera detection_labels that are not set fall through to global labels."""
        notifier = set_up(detection_labels=["car"])

        labels = notifier._get_effective_detection_labels(CAMERA_ID)

        assert labels == ["car"]

    def test_unset_camera_labels_do_not_raise_on_notification(
        self, set_up_mocked: SetUpMocked
    ):
        """Detection with unset camera labels does not raise TypeError."""
        mocks = set_up_mocked(detection_labels=["person"])
        recording = make_recording([make_detected_object("person")])
        run_async_recorder_complete(mocks.notifier, make_event(recording))

        mocks.send_message.assert_called_once()

    def test_global_comma_deprecated_label_strips_empty_entries(self, set_up: SetUp):
        """Global deprecated detection_label strips empty comma-separated entries."""
        notifier = set_up(detection_label=",person,")

        labels = notifier._get_effective_detection_labels(CAMERA_ID)

        assert "" not in labels
        assert labels == ["person"]

    def test_camera_comma_deprecated_label_strips_empty_entries(self, set_up: SetUp):
        """Camera deprecated detection_label strips empty comma-separated entries."""
        notifier = set_up(cameras={CAMERA_ID: {"detection_label": ",car,"}})

        labels = notifier._get_effective_detection_labels(CAMERA_ID)

        assert "" not in labels
        assert labels == ["car"]

    def test_returns_default_when_no_labels_configured(self, set_up: SetUp):
        """Default detection labels are returned when no labels are configured."""
        notifier = set_up(detection_labels=[])

        labels = notifier._get_effective_detection_labels(CAMERA_ID)

        assert labels == ["person"]

    @pytest.mark.parametrize(
        ("keys", "expected"),
        [
            pytest.param(
                {"detection_label": "comma", "detection_labels": ["list"]},
                ["comma"],
                id="global_comma_over_global_list",
            ),
            pytest.param(
                {"detection_label": "", "detection_labels": ["list"]},
                ["list"],
                id="global_comma_empty",
            ),
            pytest.param(
                {
                    "detection_label": "global",
                    "cameras": {CAMERA_ID: {"detection_labels": ["camera"]}},
                },
                ["camera"],
                id="camera_list_over_global_comma",
            ),
            pytest.param(
                {
                    "cameras": {
                        CAMERA_ID: {
                            "detection_label": "comma",
                            "detection_labels": ["list"],
                        }
                    }
                },
                ["comma"],
                id="camera_comma_over_camera_list",
            ),
            pytest.param(
                {"cameras": {CAMERA_ID: {"detection_label": ""}}},
                [],
                id="camera_comma_empty",
            ),
            pytest.param(
                {
                    "detection_labels": ["global"],
                    "cameras": {CAMERA_ID: {"detection_labels": []}},
                },
                ["global"],
                id="camera_list_empty",
            ),
            pytest.param(
                {
                    "detection_labels": ["global"],
                    "cameras": {CAMERA_ID: {"detection_labels": None}},
                },
                ["global"],
                id="camera_list_null",
            ),
        ],
    )
    def test_priority(self, set_up: SetUp, keys: dict[str, Any], expected: list[str]):
        """Camera labels win over global ones, detection_label wins per level."""
        notifier = set_up(**keys)

        assert notifier._get_effective_detection_labels(CAMERA_ID) == expected


class TestStop:
    """Tests for DiscordNotifier.stop."""

    def test_unsubscribes_listeners_and_stops_thread(
        self, set_up: SetUp, thread: MagicMock
    ):
        """Stop unsubscribes event listeners and stops the background thread."""
        notifier = set_up()

        listener_mocks = notifier._event_listeners
        assert len(listener_mocks) == 3

        notifier.stop()

        for listener in listener_mocks:
            cast("MagicMock", listener).assert_called_once()
        thread.return_value.stop.assert_called_once()
        thread.return_value.join.assert_called_once()


class TestDeduplication:
    """Tests for recording deduplication."""

    def test_does_not_resend_video_for_same_recording_id(
        self, set_up_mocked: SetUpMocked
    ):
        """Second complete event for same recording id does not resend video."""
        mocks = set_up_mocked(send_detection_video=True)
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
            run_async_recorder_complete(mocks.notifier, event)
            mocks.send_file.assert_called_once()

            # Reset mocks to verify second call behavior
            mocks.send_file.reset_mock()
            mocks.send_message.reset_mock()

            # Second call for the same recording id should not resend video
            run_async_recorder_complete(mocks.notifier, event)
            mocks.send_file.assert_not_called()
            mocks.send_file_partial.assert_not_called()
            mocks.send_message.assert_called_once()
