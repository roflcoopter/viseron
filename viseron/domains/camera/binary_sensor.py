"""Binary sensor that represents connection to camera."""
from viseron import EventData, Viseron
from viseron.domains.camera import EVENT_STATUS
from viseron.helpers.entity.binary_sensor import BinarySensorEntity

from . import AbstractCamera


class ConnectionStatusBinarySensor(BinarySensorEntity):
    """Entity that keeps track of connection to camera."""

    def __init__(self, vis: Viseron, camera: AbstractCamera):
        self._camera = camera
        self.object_id = f"{camera.identifier}_connected"
        self.name = f"{camera.name} Connected"

        self.device_name = camera.name
        self.device_identifiers = [camera.identifier]

        vis.listen_event(
            EVENT_STATUS.format(camera_identifier=camera.identifier),
            self.handle_event,
        )

    @property
    def _is_on(self):
        return self._camera.connected

    def handle_event(self, _: EventData):
        """Handle status event."""
        self.set_state()
