"""Image entity for a camera."""
from __future__ import annotations

from typing import TYPE_CHECKING

from viseron.helpers.entity.image import ImageEntity

from ..const import EVENT_RECORDER_START
from . import CameraEntity

if TYPE_CHECKING:
    from viseron import EventData, Viseron

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

        vis.listen_event(
            EVENT_RECORDER_START.format(camera_identifier=camera.identifier),
            self.handle_event,
        )

    def handle_event(self, event_data: EventData):
        """Handle recorder start event."""
        attributes = {}
        attributes["recording_start"] = event_data.data.start_time.isoformat()
        attributes["path"] = event_data.data.path
        if event_data.data.thumbnail_path:
            attributes["thumbnail_path"] = event_data.data.thumbnail_path

        self._state = event_data.data.thumbnail
        self._attributes = attributes
        self.set_state()
