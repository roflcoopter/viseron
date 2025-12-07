"""Toggle entity to control manual recording for NVR."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.components.storage.models import TriggerTypes
from viseron.domains.camera.const import EVENT_RECORDER_START, EVENT_RECORDER_STOP
from viseron.domains.camera.entity.toggle import CameraToggle
from viseron.domains.camera.recorder import EventRecorderData, ManualRecording
from viseron.events import Event

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.nvr.nvr import NVR


class ManualRecordingToggle(CameraToggle):
    """Entity that toggles manual recording on/off for a camera's NVR."""

    def __init__(self, vis: Viseron, nvr: NVR) -> None:
        super().__init__(vis, nvr.camera)
        self._nvr = nvr
        self.object_id = f"{nvr.camera.identifier}_manual_recording"
        self.name = f"{nvr.camera.name} Manual Recording"
        self.icon = "mdi:record"

    def setup(self) -> None:
        """Set up event listener."""
        self._vis.listen_event(
            EVENT_RECORDER_START.format(camera_identifier=self._camera.identifier),
            self.handle_event,
        )
        self._vis.listen_event(
            EVENT_RECORDER_STOP.format(camera_identifier=self._camera.identifier),
            self.handle_event,
        )

    def handle_event(self, _event_data: Event[EventRecorderData]) -> None:
        """Handle recorder start/stop event."""
        self.set_state()

    @property
    def _is_on(self):
        """Return if a manual recording is currently active."""
        return (
            self._camera.is_recording
            and self._camera.recorder.active_recording is not None
            and self._camera.recorder.active_recording.trigger_type
            == TriggerTypes.MANUAL
        )

    def turn_on(self) -> None:
        """Start an indefinite manual recording."""
        self._nvr.start_manual_recording(ManualRecording(duration=None))

    def turn_off(self) -> None:
        """Stop an ongoing manual recording."""
        self._nvr.stop_manual_recording()
