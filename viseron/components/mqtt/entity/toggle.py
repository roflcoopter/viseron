"""MQTT toggle entity."""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, TypeVar

from viseron.components.mqtt.helpers import SubscribeTopic
from viseron.components.nvr.nvr import NVR
from viseron.components.nvr.toggle import ManualRecordingToggle
from viseron.components.storage.models import TriggerTypes
from viseron.const import STATE_OFF, STATE_ON
from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.recorder import ManualRecording
from viseron.helpers.entity.toggle import ToggleEntity

from . import MQTTEntity

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)

E = TypeVar("E", bound=ToggleEntity)


class ToggleMQTTEntity(MQTTEntity[E]):
    """Base toggle MQTT entity class."""

    def __init__(self, vis: Viseron, config, entity: E) -> None:
        super().__init__(vis, config, entity)
        self._mqtt.subscribe(
            SubscribeTopic(topic=self.command_topic, callback=self.command_handler)
        )

    @property
    def command_topic(self) -> str:
        """Return command topic."""
        return (
            f"{self._mqtt.base_topic}/{self.entity.domain}/"
            f"{self.entity.object_id}/command"
        )

    def command_handler(self, message) -> None:
        """Handle commands on the command topic."""
        payload = message.payload.decode()
        if payload == STATE_ON:
            self.entity.turn_on()
        elif payload == STATE_OFF:
            self.entity.turn_off()


def _parse_manual_recording_payload(payload_raw: str) -> tuple[str | None, int | None]:
    """Parse payload into ('start'|'stop'|None, duration|None).

    Supported payloads:
      - 'on' => start
      - 'off' => stop
      - {"action":"start","duration":<seconds>}
      - {"action":"stop"}
    """
    if not payload_raw:
        return None, None

    payload = payload_raw.strip()
    # JSON payload
    if payload.startswith("{"):
        try:
            data = json.loads(payload)
            action = data.get("action")
            duration = data.get("duration")
            return action, int(duration) if duration is not None else None
        except Exception:  # pylint: disable=broad-except
            return None, None

    # Simple string payloads
    lowered = payload.lower()
    if lowered == "on":
        return "start", None
    if lowered == "off":
        return "stop", None
    return None, None


def _is_manual_recording_active(camera: AbstractCamera) -> bool:
    """Check if camera currently has an active manual recording."""
    if (
        camera.is_recording
        and camera.recorder.active_recording
        and camera.recorder.active_recording.trigger_type == TriggerTypes.MANUAL
    ):
        return True
    return False


def _handle_start_manual_recording(
    nvr: NVR, camera: AbstractCamera, duration: int | None
) -> None:
    """Start manual recording if possible."""
    if _is_manual_recording_active(camera):
        LOGGER.debug(
            f"Camera {camera.identifier} already in a manual recording, "
            "ignoring start command"
        )
        return
    if camera.current_frame is None:
        LOGGER.debug(
            f"No frame available for camera {camera.identifier}, "
            "cannot start manual recording"
        )
        return
    manual_recording = ManualRecording(duration=duration)
    nvr.start_manual_recording(manual_recording)
    LOGGER.debug(
        f"Started manual recording for camera {camera.identifier} with "
        f"{f'duration {duration}s' if duration else 'no duration'}"
    )


def _handle_stop_manual_recording(nvr: NVR, camera: AbstractCamera) -> None:
    """Stop manual recording if active."""
    if not _is_manual_recording_active(camera):
        LOGGER.debug(
            f"Stop manual recording requested for camera {camera.identifier} "
            "but no manual recording active"
        )
        return
    nvr.stop_manual_recording()


class ManualRecordingToggleMQTTEntity(ToggleMQTTEntity[ManualRecordingToggle]):
    """Manual recording toggle MQTT entity class.

    Overrides command handler to support manual recording commands.
    """

    def command_handler(self, message) -> None:
        """Handle commands on the command topic."""
        manual_recording_command_handler(self.entity.nvr, message)


def manual_recording_command_handler(nvr: NVR, message) -> None:
    """Handle manual recording command payloads for a specific camera."""
    payload_raw = message.payload.decode().strip()
    camera: AbstractCamera = nvr.camera

    if not payload_raw:
        LOGGER.error("Empty manual recording command payload, ignoring")
        return

    action, duration = _parse_manual_recording_payload(payload_raw)
    if action is None:
        LOGGER.debug(
            f"Unsupported manual recording payload '{payload_raw}' for "
            f"camera {camera.identifier}"
        )
        return

    if action not in {"start", "stop"}:
        LOGGER.debug(
            f"Unsupported manual recording action '{action}' for camera "
            f"{camera.identifier}"
        )
        return

    if duration is not None and duration <= 0:
        LOGGER.debug(
            f"Invalid manual recording duration {duration} for camera "
            f"{camera.identifier}"
        )
        return

    if action == "start":
        _handle_start_manual_recording(nvr, camera, duration)
    else:
        _handle_stop_manual_recording(nvr, camera)
