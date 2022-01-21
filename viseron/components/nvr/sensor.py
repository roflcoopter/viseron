"""Sensor that represents NVR state of operation."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.domains.camera.entity.sensor import CameraSensor

from .const import EVENT_OPERATION_STATE

if TYPE_CHECKING:
    from viseron import Event, Viseron

    from . import NVR


class OperationStateSensor(CameraSensor):
    """Entity that shows the current state of operation for nvr."""

    def __init__(
        self,
        vis: Viseron,
        nvr: NVR,
    ):
        super().__init__(vis, nvr.camera)
        self.nvr = nvr

        self.entity_category = "diagnostic"
        self.object_id = f"{nvr.camera.identifier}_operation_state"
        self.name = f"{nvr.camera.name} Operation State"

        vis.listen_event(
            EVENT_OPERATION_STATE.format(camera_identifier=nvr.camera.identifier),
            self.handle_event,
        )

    def handle_event(self, event_data: Event):
        """Update sensor state."""
        self._state = event_data.data.operation_state
        self.set_state()
