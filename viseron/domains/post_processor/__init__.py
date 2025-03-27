"""Post processing of detected objects."""
from __future__ import annotations

import logging
from abc import abstractmethod
from dataclasses import dataclass
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

import numpy as np
import voluptuous as vol
from sqlalchemy import insert

from viseron.components.storage import Storage
from viseron.components.storage.const import COMPONENT as STORAGE_COMPONENT
from viseron.components.storage.models import PostProcessorResults
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains import AbstractDomain
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.domains.object_detector.const import (
    EVENT_OBJECTS_IN_FOV,
    EVENT_OBJECTS_IN_ZONE,
)
from viseron.domains.object_detector.detected_object import (
    DetectedObject,
    EventDetectedObjectsData,
)
from viseron.helpers import apply_mask, generate_mask, generate_mask_image
from viseron.helpers.schemas import COORDINATES_SCHEMA
from viseron.helpers.validators import CameraIdentifier, CoerceNoneToDict
from viseron.types import SupportedDomains
from viseron.watchdog.thread_watchdog import RestartableThread

from .const import (
    CONFIG_CAMERAS,
    CONFIG_COORDINATES,
    CONFIG_LABELS,
    CONFIG_MASK,
    DEFAULT_MASK,
    DESC_CAMERAS,
    DESC_COORDINATES,
    DESC_LABELS_GLOBAL,
    DESC_LABELS_LOCAL,
    DESC_MASK,
)

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera.shared_frames import SharedFrame
    from viseron.domains.object_detector.zone import Zone


LABEL_SCHEMA = vol.Schema([str])

CAMERA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONFIG_LABELS, description=DESC_LABELS_LOCAL): LABEL_SCHEMA,
        vol.Optional(CONFIG_MASK, default=DEFAULT_MASK, description=DESC_MASK): [
            {
                vol.Required(
                    CONFIG_COORDINATES, description=DESC_COORDINATES
                ): COORDINATES_SCHEMA
            }
        ],
    }
)

BASE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_CAMERAS, description=DESC_CAMERAS): {
            CameraIdentifier(): vol.All(CoerceNoneToDict(), CAMERA_SCHEMA)
        },
        vol.Optional(CONFIG_LABELS, description=DESC_LABELS_GLOBAL): LABEL_SCHEMA,
    }
)


@dataclass
class PostProcessorFrame:
    """Object representing a frame that is passed to post processors."""

    camera_identifier: str
    shared_frame: SharedFrame
    frame: np.ndarray
    detected_objects: list[DetectedObject]
    filtered_objects: list[DetectedObject]
    zone: Zone | None = None


class AbstractPostProcessor(AbstractDomain):
    """Abstract Post Processor."""

    def __init__(self, vis: Viseron, config, camera_identifier) -> None:
        self._vis = vis
        self._storage: Storage = vis.data[STORAGE_COMPONENT]
        self._config = config
        self._camera_identifier = camera_identifier
        self._camera = vis.get_registered_domain(CAMERA_DOMAIN, camera_identifier)
        self._logger = logging.getLogger(f"{self.__module__}.{camera_identifier}")

        self._labels = config.get(CONFIG_LABELS, None)
        if config[CONFIG_CAMERAS][camera_identifier].get(CONFIG_LABELS, None):
            self._labels = config[CONFIG_CAMERAS][camera_identifier][CONFIG_LABELS]

        if self._labels is None:
            self._logger.debug(
                "No labels specified, post processing will run for "
                "all labels tracked by the object detector."
            )
        else:
            self._logger.debug(f"Post processor will run for labels: {self._labels}")

        self._mask = None
        if mask_config := config[CONFIG_CAMERAS][camera_identifier][CONFIG_MASK]:
            self._logger.debug("Creating mask")
            self._mask = generate_mask(mask_config)
            self._mask_image = generate_mask_image(self._mask, self._camera.resolution)

        self._kill_received = False
        self._post_processor_queue: Queue[Event[EventDetectedObjectsData]] = Queue(
            maxsize=1
        )
        processor_thread = RestartableThread(
            name=__name__, target=self.post_process, daemon=True, register=True
        )
        processor_thread.start()
        self._vis.listen_event(
            EVENT_OBJECTS_IN_FOV.format(camera_identifier=camera_identifier),
            self._post_processor_queue,
        )
        self._vis.listen_event(
            EVENT_OBJECTS_IN_ZONE.format(
                camera_identifier=camera_identifier,
                zone_name="*",
            ),
            self._post_processor_queue,
        )
        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self.stop)

    @property
    def mask(self):
        """Return post processor mask."""
        return self._mask

    def apply_mask(self, shared_frame: SharedFrame) -> np.ndarray:
        """Apply mask to frame."""
        decoded_frame = self._camera.shared_frames.get_decoded_frame_rgb(
            shared_frame
        ).copy()
        if self._mask:
            apply_mask(decoded_frame, self._mask_image)
        return decoded_frame

    def post_process(self) -> None:
        """Post processor loop."""

        def _process(
            detected_objects_data: EventDetectedObjectsData,
            filtered_objects: list[DetectedObject],
        ) -> None:
            if detected_objects_data.shared_frame is None:
                return

            with detected_objects_data.shared_frame:
                decoded_frame = self.apply_mask(detected_objects_data.shared_frame)
                preprocessed_frame = self.preprocess(decoded_frame)
                self.process(
                    PostProcessorFrame(
                        camera_identifier=detected_objects_data.camera_identifier,
                        shared_frame=detected_objects_data.shared_frame,
                        frame=preprocessed_frame,
                        detected_objects=detected_objects_data.objects,
                        filtered_objects=filtered_objects,
                        zone=detected_objects_data.zone,
                    )
                )

        while not self._kill_received:
            try:
                event_data = self._post_processor_queue.get(timeout=1)
            except Empty:
                continue

            detected_objects_data = event_data.data

            if detected_objects_data.shared_frame is None:
                self._logger.debug("No frame, skipping post processing")
                continue

            if self._labels:
                filtered_objects = [
                    detected_object
                    for detected_object in detected_objects_data.objects
                    if detected_object.label in self._labels
                ]
                if filtered_objects:
                    _process(detected_objects_data, filtered_objects)
            elif detected_objects_data.objects:
                _process(detected_objects_data, detected_objects_data.objects)

        self._logger.debug(f"Post processor {self.__class__.__name__} stopped")

    @abstractmethod
    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Perform preprocessing of frame before running post processor."""

    @abstractmethod
    def process(self, post_processor_frame: PostProcessorFrame):
        """Process frame."""

    def _insert_result(
        self, domain: SupportedDomains, snapshot_path: str | None, data: dict[str, Any]
    ) -> None:
        """Insert face recognition result into database."""
        with self._storage.get_session() as session:
            stmt = insert(PostProcessorResults).values(
                camera_identifier=self._camera.identifier,
                domain=domain,
                snapshot_path=snapshot_path,
                data=data,
            )
            session.execute(stmt)
            session.commit()

    def stop(self) -> None:
        """Stop post processor."""
        self._kill_received = True
