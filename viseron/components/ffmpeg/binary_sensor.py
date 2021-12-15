"""Binary sensor that represents connection to camera."""
from viseron import EventData, Viseron
from viseron.domains.camera import EVENT_STATUS
from viseron.helpers.entity.binary_sensor import BinarySensorEntity


class ConnectionStatusBinarySensor(BinarySensorEntity):
    """Entity that keeps track of connection to camera."""

    def __init__(self, vis: Viseron, camera, name):
        self._camera = camera
        self._name = name

        vis.listen_event(
            EVENT_STATUS.format(camera_identifier=self._camera.identifier),
            self.handle_event,
        )

    @property
    def _is_on(self):
        return self._camera.connected

    def handle_event(self, _: EventData):
        """Handle status event."""
        self.set_state()
