"""Image entity for a camera."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from viseron.components.storage.const import LATEST_SNAPSHOT_FILENAME
from viseron.domains.camera.const import EVENT_RECORDER_START
from viseron.helpers import utcnow
from viseron.helpers.entity.image import ImageEntity

from . import CameraEntity

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera import AbstractCamera
    from viseron.domains.camera.recorder import EventRecorderData
    from viseron.viseron_types import SnapshotDomain


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
        self._event_listeners.append(
            self._vis.listen_event(
                EVENT_RECORDER_START.format(camera_identifier=self._camera.identifier),
                self.handle_event,
            )
        )

    @property
    def extra_attributes(self) -> dict:
        """Return extra attributes."""
        return {
            "start_time": self._attr_start_time,
            "thumbnail_path": self._attr_thumbnail_path,
        }

    def handle_event(self, event_data: Event[EventRecorderData]) -> None:
        """Handle recorder start event."""
        recording = event_data.data.recording
        self._attr_start_time = recording.start_time.isoformat()
        self._attr_thumbnail_path = recording.thumbnail_path
        self._image = recording.thumbnail
        self.set_state()


class LatestSnapshotImage(CameraImage):
    """Entity that keeps track of the latest snapshot of a domain."""

    def __init__(
        self,
        vis: Viseron,
        camera: AbstractCamera,
        snapshot_domain: SnapshotDomain,
    ) -> None:
        super().__init__(vis, camera)
        self.object_id = f"{camera.identifier}_latest_{snapshot_domain.value}_snapshot"
        self.name = (
            f"{camera.name} Latest "
            f"{snapshot_domain.value.replace('_', ' ').title()} Snapshot"
        )
        self.icon = "mdi:image"

        self._attr_snapshot_path: str | None = None
        self._attr_updated_at: str | None = None
        self._unloaded = False

    @property
    def extra_attributes(self) -> dict:
        """Return extra attributes."""
        return {
            "snapshot_path": self._attr_snapshot_path,
            "latest_snapshot_filename": LATEST_SNAPSHOT_FILENAME,
            "updated_at": self._attr_updated_at,
        }

    def update_snapshot(self, frame: np.ndarray, snapshot_path: str) -> None:
        """Store the latest snapshot frame and publish a new state."""
        if self._unloaded:
            return

        # zoom_boundingbox returns a slice view that keeps the full resolution frame
        # alive, so copy it into a standalone array before retaining it.
        self._image = np.ascontiguousarray(frame)
        self._attr_snapshot_path = snapshot_path
        self._attr_updated_at = utcnow().isoformat()
        self.set_state()

    def unload(self) -> None:
        """Unload entity.

        set_state after unload would resurrect the entity in the states registry,
        so updates are refused once unloaded.
        """
        super().unload()
        self._unloaded = True
        self._image = None
