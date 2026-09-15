"""Image entity for a post processor."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from viseron.components.storage.const import LATEST_SNAPSHOT_FILENAME
from viseron.domains.camera.entity.image import CameraImage
from viseron.helpers import utcnow

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.camera import AbstractCamera
    from viseron.viseron_types import SnapshotDomain


class PostProcessorSnapshotImage(CameraImage):
    """Entity that keeps track of the latest snapshot of a post processor."""

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
