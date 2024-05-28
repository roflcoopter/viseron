"""Post processing of detected objects."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from queue import Queue
from typing import TYPE_CHECKING

import voluptuous as vol

from viseron.components.storage import Storage
from viseron.components.storage.const import COMPONENT as STORAGE_COMPONENT
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.domains.object_detector.const import (
    EVENT_OBJECTS_IN_FOV,
    EVENT_OBJECTS_IN_ZONE,
)
from viseron.domains.object_detector.detected_object import (
    DetectedObject,
    EventDetectedObjectsData,
)
from viseron.helpers.validators import CameraIdentifier, CoerceNoneToDict
from viseron.watchdog.thread_watchdog import RestartableThread

from .const import (
    CONFIG_CAMERAS,
    CONFIG_LABELS,
    DESC_CAMERAS,
    DESC_LABELS_GLOBAL,
    DESC_LABELS_LOCAL,
)

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera.shared_frames import SharedFrame
    from viseron.domains.object_detector.zone import Zone


LABEL_SCHEMA = vol.Schema([str])

CAMERA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONFIG_LABELS, description=DESC_LABELS_LOCAL): LABEL_SCHEMA,
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
    detected_objects: list[DetectedObject]
    filtered_objects: list[DetectedObject]
    zone: Zone | None = None


class AbstractPostProcessor(ABC):
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

    def post_process(self) -> None:
        """Post processor loop."""
        while True:
            event_data = self._post_processor_queue.get()
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
                    self.process(
                        PostProcessorFrame(
                            camera_identifier=detected_objects_data.camera_identifier,
                            shared_frame=detected_objects_data.shared_frame,
                            detected_objects=detected_objects_data.objects,
                            filtered_objects=filtered_objects,
                            zone=detected_objects_data.zone,
                        )
                    )
            elif detected_objects_data.objects:
                self.process(
                    PostProcessorFrame(
                        camera_identifier=detected_objects_data.camera_identifier,
                        shared_frame=detected_objects_data.shared_frame,
                        detected_objects=detected_objects_data.objects,
                        filtered_objects=detected_objects_data.objects,
                        zone=detected_objects_data.zone,
                    )
                )

    @abstractmethod
    def process(self, post_processor_frame: PostProcessorFrame):
        """Process frame."""
