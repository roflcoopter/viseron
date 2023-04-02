"""Image entity for a camera."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.helpers.entity.image import ImageEntity

from ..const import EVENT_RECORDER_START
from . import CameraEntity

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera.recorder import EventRecorderData

    from .. import AbstractCamera


class CameraImage(CameraEntity, ImageEntity):
    """Base class for an image that is tied to a specific AbstractCamera."""


class ThumbnailImage(CameraImage):
    """Entity that keeps track of the latest thumbnail of a camera."""

    def __init__(self, vis: Viseron, camera: AbstractCamera) -> None:
        super().__init__(vis, camera)
        self.device_class = "running"
        self.object_id = f"{camera.identifier}_latest_thumbnail"
        self.name = f"{camera.name} Latest Thumbnail"

        self._attr_start_time: str | None = None
        self._attr_path: str | None = None
        self._attr_thumbnail_path: str | None = None

    def setup(self) -> None:
        """Set up event listener."""
        self._vis.listen_event(
            EVENT_RECORDER_START.format(camera_identifier=self._camera.identifier),
            self.handle_event,
        )

    @property
    def extra_attributes(self):
        """Return extra attributes."""
        return {
            "start_time": self._attr_start_time,
            "path": self._attr_path,
            "thumbnail_path": self._attr_thumbnail_path,
        }

    def handle_event(self, event_data: Event[EventRecorderData]) -> None:
        """Handle recorder start event."""
        recording = event_data.data.recording
        self._attr_start_time = recording.start_time.isoformat()
        self._attr_path = recording.path
        self._attr_thumbnail_path = recording.thumbnail_path
        self._image = recording.thumbnail
        self.set_state()
