"""Image entity for a camera."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.helpers.entity.image import ImageEntity

from ..const import EVENT_RECORDER_START
from . import CameraEntity

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera.recorder import EventRecorderStart

    from .. import AbstractCamera


class CameraImage(CameraEntity, ImageEntity):
    """Base class for an image that is tied to a specific AbstractCamera."""


class ThumbnailImage(CameraImage):
    """Entity that keeps track of the latest thumbnail of a camera."""

    def __init__(self, vis: Viseron, camera: AbstractCamera):
        super().__init__(vis, camera)
        self.device_class = "running"
        self.object_id = f"{camera.identifier}_latest_thumbnail"
        self.name = f"{camera.name} Latest Thumbnail"

        self._attr_start_time: str | None = None
        self._attr_path: str | None = None
        self._attr_thumbnail_path: str | None = None

    def setup(self):
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

    def handle_event(self, event_data: Event[EventRecorderStart]):
        """Handle recorder start event."""
        self._attr_start_time = event_data.data.start_time.isoformat()
        self._attr_path = event_data.data.path
        self._attr_thumbnail_path = event_data.data.thumbnail_path
        self._image = event_data.data.thumbnail
        self.set_state()
