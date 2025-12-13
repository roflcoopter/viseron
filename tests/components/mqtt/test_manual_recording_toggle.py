"""Tests for the Manual Recording MQTT toggle entity."""

# pylint: disable=redefined-outer-name

import json
import types
from unittest.mock import MagicMock, Mock

import pytest

from viseron.components.mqtt import MQTT
from viseron.components.mqtt.const import COMPONENT as MQTT_COMPONENT
from viseron.components.mqtt.entity.toggle import (
    ManualRecordingToggleMQTTEntity,
    manual_recording_command_handler,
)
from viseron.components.storage.models import TriggerTypes
from viseron.domains.camera.recorder import ManualRecording

from tests.common import MockCamera
from tests.conftest import MockViseron


class DummyMessage:
    """Dummy MQTT message."""

    def __init__(self, payload):
        self.payload = payload


def make_message(payload) -> DummyMessage:
    """Create a dummy MQTT message; JSON-encode dicts/lists."""
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload)
    return DummyMessage(payload=str(payload).encode())


@pytest.fixture
def nvr(vis):
    """Mock NVR with a camera and start/stop methods."""
    camera = MockCamera(vis=None, identifier="cam-1")
    camera.is_recording = False
    camera.current_frame = object()
    return types.SimpleNamespace(
        camera=camera,
        start_manual_recording=Mock(),
        stop_manual_recording=Mock(),
    )


def test_start_on_string_starts_recording(nvr):
    """'on' payload starts manual recording."""
    msg = make_message("on")
    nvr.camera.is_recording = False
    manual_recording_command_handler(nvr, msg)
    assert nvr.start_manual_recording.call_count == 1
    args, _ = nvr.start_manual_recording.call_args
    assert isinstance(args[0], ManualRecording)
    assert args[0].duration is None


def test_stop_off_string_stops_recording(nvr):
    """'off' payload stops manual recording."""
    msg = make_message("off")
    nvr.camera.is_recording = True
    nvr.camera.recorder.active_recording = types.SimpleNamespace(
        trigger_type=TriggerTypes.MANUAL
    )
    manual_recording_command_handler(nvr, msg)
    nvr.stop_manual_recording.assert_called_once()


def test_json_start_with_duration(nvr):
    """JSON start with duration sets the duration."""
    msg = make_message({"action": "start", "duration": 5})
    manual_recording_command_handler(nvr, msg)
    nvr.start_manual_recording.assert_called_once()
    manual = nvr.start_manual_recording.call_args[0][0]
    assert isinstance(manual, ManualRecording)
    assert manual.duration == 5


def test_json_start_without_duration(nvr):
    """JSON start without duration uses no duration."""
    msg = make_message({"action": "start"})
    manual_recording_command_handler(nvr, msg)
    nvr.start_manual_recording.assert_called_once()
    manual = nvr.start_manual_recording.call_args[0][0]
    assert manual.duration is None


def test_json_stop(nvr):
    """JSON stop stops active manual recording."""
    nvr.camera.is_recording = True
    nvr.camera.recorder.active_recording = types.SimpleNamespace(
        trigger_type=TriggerTypes.MANUAL
    )
    msg = make_message({"action": "stop"})
    manual_recording_command_handler(nvr, msg)
    nvr.stop_manual_recording.assert_called_once()


def test_invalid_payload_does_nothing(nvr):
    """Invalid payload does not trigger start/stop."""
    msg = make_message("invalid")
    manual_recording_command_handler(nvr, msg)
    nvr.start_manual_recording.assert_not_called()
    nvr.stop_manual_recording.assert_not_called()


def test_invalid_json_does_nothing(nvr):
    """Malformed JSON does not trigger start/stop."""
    msg = make_message('{"action":')
    manual_recording_command_handler(nvr, msg)
    nvr.start_manual_recording.assert_not_called()
    nvr.stop_manual_recording.assert_not_called()


def test_invalid_duration_does_nothing(nvr):
    """Non-positive duration is ignored."""
    msg = make_message({"action": "start", "duration": 0})
    manual_recording_command_handler(nvr, msg)
    nvr.start_manual_recording.assert_not_called()


def test_already_manual_recording_ignores_start(nvr):
    """Start is ignored if manual recording is already active."""
    nvr.camera.is_recording = True
    nvr.camera.recorder.active_recording = types.SimpleNamespace(
        trigger_type=TriggerTypes.MANUAL
    )
    msg = make_message("on")
    manual_recording_command_handler(nvr, msg)
    nvr.start_manual_recording.assert_not_called()


def test_no_current_frame_ignores_start(nvr):
    """Start is ignored if there is no current frame."""
    nvr.camera.current_frame = None
    msg = make_message("on")
    manual_recording_command_handler(nvr, msg)
    nvr.start_manual_recording.assert_not_called()


def test_stop_when_no_manual_recording_does_nothing(nvr):
    """Stop is ignored when no manual recording is active."""
    nvr.camera.is_recording = True
    nvr.camera.recorder.active_recording = types.SimpleNamespace(trigger_type="other")
    msg = make_message("off")
    manual_recording_command_handler(nvr, msg)
    nvr.stop_manual_recording.assert_not_called()


def test_entity_command_handler_routes_to_handler(vis: MockViseron, nvr, monkeypatch):
    """MQTT entity forwards messages to the command handler."""
    vis.data[MQTT_COMPONENT] = MagicMock(spec=MQTT)
    toggle = types.SimpleNamespace(nvr=nvr, domain="nvr", object_id="manual_recording")
    config = {"client_id": "vis"}
    entity = ManualRecordingToggleMQTTEntity(
        vis, config, toggle  # type: ignore[arg-type]
    )

    spy = Mock()
    monkeypatch.setattr(
        "viseron.components.mqtt.entity.toggle.manual_recording_command_handler", spy
    )
    message = make_message("on")
    entity.command_handler(message)
    spy.assert_called_once_with(nvr, message)
