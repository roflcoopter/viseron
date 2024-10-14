"""EdgeTPU image classification post processor."""
from __future__ import annotations

import threading
from queue import Queue
from typing import TYPE_CHECKING

import cv2
import numpy as np

from viseron.domains.image_classification import (
    AbstractImageClassification,
    ImageClassificationResult,
)
from viseron.domains.image_classification.const import DOMAIN
from viseron.exceptions import DomainNotReady
from viseron.helpers import calculate_absolute_coords

from . import EdgeTPUClassification, MakeInterpreterError
from .const import COMPONENT, CONFIG_CROP_CORRECTION, CONFIG_IMAGE_CLASSIFICATION

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.post_processor import PostProcessorFrame

MAKE_INTERPRETER_LOCK = threading.Lock()


def setup(vis: Viseron, config, identifier) -> bool:
    """Set up the edgetpu image_classification domain."""
    with MAKE_INTERPRETER_LOCK:
        if not vis.data[COMPONENT].get(CONFIG_IMAGE_CLASSIFICATION, None):
            try:
                vis.data[COMPONENT][
                    CONFIG_IMAGE_CLASSIFICATION
                ] = EdgeTPUClassification(
                    vis,
                    config[CONFIG_IMAGE_CLASSIFICATION],
                    CONFIG_IMAGE_CLASSIFICATION,
                )
            except (MakeInterpreterError, FileNotFoundError) as error:
                raise DomainNotReady from error

    ImageClassification(vis, COMPONENT, config[DOMAIN], identifier)

    return True


class ImageClassification(AbstractImageClassification):
    """Perform EdgeTPU image classification."""

    def __init__(self, vis, component, config, camera_identifier) -> None:
        self._edgetpu: EdgeTPUClassification = vis.data[COMPONENT][
            CONFIG_IMAGE_CLASSIFICATION
        ]
        self._classification_result_queue: Queue[
            list[ImageClassificationResult]
        ] = Queue(maxsize=1)
        super().__init__(vis, component, config, camera_identifier)

    def preprocess(self, post_processor_frame: PostProcessorFrame) -> np.ndarray:
        """Perform preprocessing of frame before running classification."""
        decoded_frame = self._camera.shared_frames.get_decoded_frame_rgb(
            post_processor_frame.shared_frame
        )

        return decoded_frame

    def image_classification(
        self, frame: np.ndarray, post_processor_frame: PostProcessorFrame
    ) -> list[ImageClassificationResult]:
        """Perform image classification."""
        image_classifications = []
        for detected_object in post_processor_frame.filtered_objects:
            x1, y1, x2, y2 = calculate_absolute_coords(
                (
                    detected_object.rel_x1,
                    detected_object.rel_y1,
                    detected_object.rel_x2,
                    detected_object.rel_y2,
                ),
                self._camera.resolution,
            )
            cropped_frame = crop_frame(
                frame,
                self._camera.resolution[0],
                self._camera.resolution[1],
                x1,
                y1,
                x2,
                y2,
                self._config[CONFIG_CROP_CORRECTION],
            )
            resized_frame = cv2.resize(
                cropped_frame, (self.model_width, self.model_height)
            )
            result = self._edgetpu.invoke(
                resized_frame,
                self._camera_identifier,
                self._classification_result_queue,
                self._camera.resolution,
            )
            if result:
                image_classifications.append(result)
        return image_classifications

    @property
    def model_width(self) -> int:
        """Return trained model width."""
        return self._edgetpu.model_width

    @property
    def model_height(self) -> int:
        """Return trained model height."""
        return self._edgetpu.model_height


def crop_frame(frame, max_width, max_height, x1, y1, x2, y2, crop_correction):
    """Crop frame to object."""
    return frame[
        max(y1 - crop_correction, 0) : min(y2 + crop_correction, max_height),
        max(x1 - crop_correction, 0) : min(x2 + crop_correction, max_width),
    ].copy()
