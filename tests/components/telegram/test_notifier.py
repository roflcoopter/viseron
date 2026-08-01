"""Tests for TelegramEventNotifier detection_label filtering."""

from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from viseron.components.storage.models import TriggerTypes
from viseron.components.telegram import TelegramEventNotifier
from viseron.components.telegram.const import (
    CONFIG_CAMERAS,
    CONFIG_DETECTION_LABEL,
    CONFIG_DETECTION_LABELS,
    CONFIG_SEND_MESSAGE,
    CONFIG_SEND_THUMBNAIL,
    CONFIG_SEND_VIDEO,
    CONFIG_TELEGRAM_BOT_TOKEN,
    CONFIG_TELEGRAM_CHAT_IDS,
    CONFIG_TELEGRAM_LOG_IDS,
    CONFIG_TELEGRAM_USER_IDS,
    DEFAULT_DETECTION_LABELS,
    DEFAULT_SEND_MESSAGE,
    DEFAULT_TELEGRAM_LOG_IDS,
    DEFAULT_TELEGRAM_USER_IDS,
)
from viseron.domains.camera.recorder import EventRecorderData, Recording
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.events import Event
from viseron.helpers.validators import UNDEFINED

if TYPE_CHECKING:
    from tests.conftest import MockViseron

CAMERA_ID = "test_camera"


def make_config(
    detection_labels: list[str] | None = None,
    cameras: dict | None = None,
) -> dict:
    """Build a minimal TelegramEventNotifier config."""
    return {
        CONFIG_TELEGRAM_BOT_TOKEN: "token",
        CONFIG_TELEGRAM_CHAT_IDS: [123],
        CONFIG_TELEGRAM_USER_IDS: DEFAULT_TELEGRAM_USER_IDS,
        CONFIG_TELEGRAM_LOG_IDS: DEFAULT_TELEGRAM_LOG_IDS,
        CONFIG_DETECTION_LABELS: detection_labels
        if detection_labels is not None
        else DEFAULT_DETECTION_LABELS,
        CONFIG_SEND_THUMBNAIL: False,
        CONFIG_SEND_VIDEO: False,
        CONFIG_SEND_MESSAGE: DEFAULT_SEND_MESSAGE,
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


def make_recording(objects: list[DetectedObject]) -> Recording:
    """Build a minimal Recording with the given detected objects."""
    return Recording(
        id=1,
        start_time=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
        start_timestamp=0.0,
        end_time=datetime.datetime(2025, 1, 1, 0, 0, 10, tzinfo=datetime.timezone.utc),
        end_timestamp=10.0,
        date="2025-01-01",
        thumbnail=None,
        thumbnail_path=None,
        clip_path=None,
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
def notifier(vis: MockViseron) -> Any:
    """Return a TelegramEventNotifier with mocked internals."""
    config = make_config()
    with (
        patch("viseron.components.telegram.Bot"),
        patch("viseron.components.telegram.Application"),
    ):
        n = TelegramEventNotifier(vis, config)
    # Replace bot with an AsyncMock so send_* calls can be awaited
    n._bot = MagicMock()
    n._bot.send_message = AsyncMock()
    n._bot.send_video = AsyncMock()
    n._bot.send_photo = AsyncMock()
    return n


def run_send_notifications(
    notifier: TelegramEventNotifier, event: Event[EventRecorderData]
):
    """Run _send_notifications synchronously via a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(notifier._send_notifications(event))
    finally:
        loop.close()


class TestDetectionLabelFiltering:
    """Tests for detection_label filtering in _send_notifications."""

    def test_sends_when_label_matches_global(self, notifier: Any):
        """Notification sent when detected object matches global detection_labels."""
        recording = make_recording([make_detected_object("person")])
        event = make_event(recording)
        notifier._config[CONFIG_SEND_MESSAGE] = True

        run_send_notifications(notifier, event)

        notifier._bot.send_message.assert_awaited_once()

    def test_skips_when_label_does_not_match_global(self, notifier: Any):
        """No notification sent when detected object does not match detection_labels."""
        recording = make_recording([make_detected_object("car")])
        event = make_event(recording)
        notifier._config[CONFIG_DETECTION_LABELS] = ["person"]
        notifier._config[CONFIG_SEND_MESSAGE] = True

        run_send_notifications(notifier, event)

        notifier._bot.send_message.assert_not_awaited()
        notifier._bot.send_video.assert_not_awaited()
        notifier._bot.send_photo.assert_not_awaited()

    def test_sends_for_manual_recording_with_no_objects(self, notifier: Any):
        """Notification always sent when recording has no detected objects."""
        recording = make_recording([])
        recording.trigger_type = TriggerTypes.MANUAL
        event = make_event(recording)
        notifier._config[CONFIG_DETECTION_LABELS] = ["person"]
        notifier._config[CONFIG_SEND_MESSAGE] = True

        run_send_notifications(notifier, event)

        notifier._bot.send_message.assert_awaited_once()

    def test_comma_separated_labels_match(self, notifier: Any):
        """Notification sent when comma-separated detection_label matches."""
        recording = make_recording([make_detected_object("cat")])
        event = make_event(recording)
        notifier._config[CONFIG_DETECTION_LABELS] = None
        notifier._config[CONFIG_DETECTION_LABEL] = "person,cat"
        notifier._config[CONFIG_SEND_MESSAGE] = True

        run_send_notifications(notifier, event)

        notifier._bot.send_message.assert_awaited_once()

    def test_comma_separated_labels_no_match(self, notifier: Any):
        """No notification when comma-separated detection_label has no match."""
        recording = make_recording([make_detected_object("car")])
        event = make_event(recording)
        notifier._config[CONFIG_DETECTION_LABELS] = None
        notifier._config[CONFIG_DETECTION_LABEL] = "person,cat"
        notifier._config[CONFIG_SEND_MESSAGE] = True

        run_send_notifications(notifier, event)

        notifier._bot.send_message.assert_not_awaited()

    def test_camera_level_comma_separated_overrides_global(self, notifier: Any):
        """Camera-level comma-separated labels override global labels."""
        recording = make_recording([make_detected_object("dog")])
        event = make_event(recording)
        notifier._config[CONFIG_DETECTION_LABELS] = ["person"]
        notifier._config[CONFIG_CAMERAS][CAMERA_ID] = {
            CONFIG_DETECTION_LABEL: "dog,cat"
        }
        notifier._config[CONFIG_SEND_MESSAGE] = True

        run_send_notifications(notifier, event)

        notifier._bot.send_message.assert_awaited_once()

    def test_camera_level_list_overrides_global(self, notifier: Any):
        """Camera-level list labels override global labels."""
        recording = make_recording([make_detected_object("dog")])
        event = make_event(recording)
        notifier._config[CONFIG_DETECTION_LABELS] = ["person"]
        notifier._config[CONFIG_CAMERAS][CAMERA_ID] = {
            CONFIG_DETECTION_LABELS: ["dog", "cat"]
        }
        notifier._config[CONFIG_SEND_MESSAGE] = True

        run_send_notifications(notifier, event)

        notifier._bot.send_message.assert_awaited_once()

    def test_camera_comma_separated_overrides_camera_list(self, notifier: Any):
        """Camera-level comma-separated labels have higher priority than list."""
        recording = make_recording([make_detected_object("bird")])
        event = make_event(recording)
        notifier._config[CONFIG_CAMERAS][CAMERA_ID] = {
            CONFIG_DETECTION_LABEL: "bird",
            CONFIG_DETECTION_LABELS: ["person"],
        }
        notifier._config[CONFIG_SEND_MESSAGE] = True

        run_send_notifications(notifier, event)

        notifier._bot.send_message.assert_awaited_once()

    def test_multiple_cameras_independent_configs(self, notifier: Any):
        """Multiple cameras can have independent label configurations."""
        camera2_id = "camera_2"
        notifier._config[CONFIG_CAMERAS] = {
            CAMERA_ID: {CONFIG_DETECTION_LABELS: ["person"]},
            camera2_id: {CONFIG_DETECTION_LABELS: ["car"]},
        }

        # Test camera 1 with person
        recording = make_recording([make_detected_object("person")])
        event_cam1 = make_event(recording)
        event_cam1.data.camera.identifier = CAMERA_ID  # type: ignore[misc]
        notifier._config[CONFIG_SEND_MESSAGE] = True

        run_send_notifications(notifier, event_cam1)
        notifier._bot.send_message.assert_awaited_once()

        notifier._bot.send_message.reset_mock()

        # Test camera 1 with car (should not send)
        recording2 = make_recording([make_detected_object("car")])
        event_cam1_car = make_event(recording2)
        event_cam1_car.data.camera.identifier = CAMERA_ID  # type: ignore[misc]

        run_send_notifications(notifier, event_cam1_car)
        notifier._bot.send_message.assert_not_awaited()


class TestGetEffectiveDetectionLabels:
    """Unit tests for _get_effective_detection_labels method."""

    @pytest.fixture
    def notifier(self, vis: MockViseron) -> Any:
        """Return a TelegramEventNotifier with mocked internals."""
        config = make_config()
        with (
            patch("viseron.components.telegram.Bot"),
            patch("viseron.components.telegram.Application"),
        ):
            return TelegramEventNotifier(vis, config)

    def test_returns_default_when_no_config(self, notifier: Any):
        """Returns DEFAULT_DETECTION_LABELS when no config is set."""
        result = notifier._get_effective_detection_labels(CAMERA_ID)
        assert result == DEFAULT_DETECTION_LABELS

    def test_global_list_config(self, notifier: Any):
        """Returns global CONFIG_DETECTION_LABELS when set."""
        notifier._config[CONFIG_DETECTION_LABELS] = ["person", "dog"]
        result = notifier._get_effective_detection_labels(CAMERA_ID)
        assert result == ["person", "dog"]

    def test_global_comma_separated_config(self, notifier: Any):
        """Parses and returns global CONFIG_DETECTION_LABEL (comma-separated)."""
        notifier._config[CONFIG_DETECTION_LABELS] = None
        notifier._config[CONFIG_DETECTION_LABEL] = "person,dog,cat"
        result = notifier._get_effective_detection_labels(CAMERA_ID)
        assert result == ["person", "dog", "cat"]

    def test_comma_separated_with_whitespace(self, notifier: Any):
        """Trims whitespace from comma-separated labels."""
        notifier._config[CONFIG_DETECTION_LABELS] = None
        notifier._config[CONFIG_DETECTION_LABEL] = " person , dog , cat "
        result = notifier._get_effective_detection_labels(CAMERA_ID)
        assert result == ["person", "dog", "cat"]

    def test_comma_separated_with_empty_entries(self, notifier: Any):
        """Removes empty entries from comma-separated labels."""
        notifier._config[CONFIG_DETECTION_LABELS] = None
        notifier._config[CONFIG_DETECTION_LABEL] = "person,,dog,,,cat"
        result = notifier._get_effective_detection_labels(CAMERA_ID)
        assert result == ["person", "dog", "cat"]

    def test_camera_level_list_overrides_global_list(self, notifier: Any):
        """Camera-level CONFIG_DETECTION_LABELS overrides global list."""
        notifier._config[CONFIG_DETECTION_LABELS] = ["global_person"]
        notifier._config[CONFIG_CAMERAS][CAMERA_ID] = {
            CONFIG_DETECTION_LABELS: ["camera_person"]
        }
        result = notifier._get_effective_detection_labels(CAMERA_ID)
        assert result == ["camera_person"]

    def test_camera_level_list_overrides_global_comma_separated(self, notifier: Any):
        """Camera-level CONFIG_DETECTION_LABELS overrides global comma-separated."""
        notifier._config[CONFIG_DETECTION_LABELS] = None
        notifier._config[CONFIG_DETECTION_LABEL] = "global_person,global_dog"
        notifier._config[CONFIG_CAMERAS][CAMERA_ID] = {
            CONFIG_DETECTION_LABELS: ["camera_person"]
        }
        result = notifier._get_effective_detection_labels(CAMERA_ID)
        assert result == ["camera_person"]

    def test_camera_comma_separated_overrides_global_list(self, notifier: Any):
        """Camera-level CONFIG_DETECTION_LABEL overrides global list."""
        notifier._config[CONFIG_DETECTION_LABELS] = ["global_person"]
        notifier._config[CONFIG_CAMERAS][CAMERA_ID] = {
            CONFIG_DETECTION_LABEL: "camera_person,camera_dog"
        }
        result = notifier._get_effective_detection_labels(CAMERA_ID)
        assert result == ["camera_person", "camera_dog"]

    def test_camera_comma_separated_overrides_global_comma_separated(
        self, notifier: Any
    ):
        """Camera-level CONFIG_DETECTION_LABEL overrides global comma-separated."""
        notifier._config[CONFIG_DETECTION_LABELS] = None
        notifier._config[CONFIG_DETECTION_LABEL] = "global_person,global_dog"
        notifier._config[CONFIG_CAMERAS][CAMERA_ID] = {
            CONFIG_DETECTION_LABEL: "camera_person"
        }
        result = notifier._get_effective_detection_labels(CAMERA_ID)
        assert result == ["camera_person"]

    def test_camera_comma_separated_has_priority_over_camera_list(self, notifier: Any):
        """Camera-level CONFIG_DETECTION_LABEL > CONFIG_DETECTION_LABELS."""
        notifier._config[CONFIG_CAMERAS][CAMERA_ID] = {
            CONFIG_DETECTION_LABEL: "comma_label",
            CONFIG_DETECTION_LABELS: ["list_label"],
        }
        result = notifier._get_effective_detection_labels(CAMERA_ID)
        assert result == ["comma_label"]

    def test_undefined_camera_list_falls_back_to_global(self, notifier: Any):
        """Undefined camera CONFIG_DETECTION_LABELS falls back to global."""
        notifier._config[CONFIG_DETECTION_LABELS] = ["global_person"]
        notifier._config[CONFIG_CAMERAS][CAMERA_ID] = {
            CONFIG_DETECTION_LABELS: UNDEFINED
        }
        result = notifier._get_effective_detection_labels(CAMERA_ID)
        assert result == ["global_person"]

    def test_empty_camera_config_uses_global(self, notifier: Any):
        """Empty camera config falls back to global config."""
        notifier._config[CONFIG_DETECTION_LABELS] = ["global_person"]
        notifier._config[CONFIG_CAMERAS][CAMERA_ID] = {}
        result = notifier._get_effective_detection_labels(CAMERA_ID)
        assert result == ["global_person"]

    def test_unknown_camera_uses_global(self, notifier: Any):
        """Unknown camera identifier uses global config."""
        notifier._config[CONFIG_DETECTION_LABELS] = ["global_person"]
        result = notifier._get_effective_detection_labels("unknown_camera")
        assert result == ["global_person"]

    def test_priority_order_all_levels(self, notifier: Any):
        """Test priority order.

        Correct priority order: camera_comma > camera_list > global_comma > global_list.
        """
        global_list = ["global_list"]
        global_comma = "global_comma"
        camera_list = ["camera_list"]
        camera_comma = "camera_comma"

        # Test 1: Only global list
        notifier._config[CONFIG_DETECTION_LABELS] = global_list
        notifier._config[CONFIG_DETECTION_LABEL] = None
        notifier._config[CONFIG_CAMERAS][CAMERA_ID] = {}
        assert notifier._get_effective_detection_labels(CAMERA_ID) == global_list

        # Test 2: Global comma overrides global list
        notifier._config[CONFIG_DETECTION_LABELS] = global_list
        notifier._config[CONFIG_DETECTION_LABEL] = global_comma
        notifier._config[CONFIG_CAMERAS][CAMERA_ID] = {}
        assert notifier._get_effective_detection_labels(CAMERA_ID) == [global_comma]

        # Test 3: Camera list overrides both global
        notifier._config[CONFIG_DETECTION_LABELS] = global_list
        notifier._config[CONFIG_DETECTION_LABEL] = global_comma
        notifier._config[CONFIG_CAMERAS][CAMERA_ID] = {
            CONFIG_DETECTION_LABELS: camera_list
        }
        assert notifier._get_effective_detection_labels(CAMERA_ID) == camera_list

        # Test 4: Camera comma overrides everything
        notifier._config[CONFIG_DETECTION_LABELS] = global_list
        notifier._config[CONFIG_DETECTION_LABEL] = global_comma
        notifier._config[CONFIG_CAMERAS][CAMERA_ID] = {
            CONFIG_DETECTION_LABELS: camera_list,
            CONFIG_DETECTION_LABEL: camera_comma,
        }
        assert notifier._get_effective_detection_labels(CAMERA_ID) == [camera_comma]

    def test_single_item_comma_separated(self, notifier: Any):
        """Handles single item in comma-separated string."""
        notifier._config[CONFIG_DETECTION_LABELS] = None
        notifier._config[CONFIG_DETECTION_LABEL] = "person"
        result = notifier._get_effective_detection_labels(CAMERA_ID)
        assert result == ["person"]

    def test_camera_single_item_comma_separated(self, notifier: Any):
        """Handles single item in camera-level comma-separated string."""
        notifier._config[CONFIG_DETECTION_LABELS] = ["global"]
        notifier._config[CONFIG_CAMERAS][CAMERA_ID] = {
            CONFIG_DETECTION_LABEL: "camera_person"
        }
        result = notifier._get_effective_detection_labels(CAMERA_ID)
        assert result == ["camera_person"]
