"""EdgeTPU image classification post processor."""
from __future__ import annotations

from queue import Queue
from typing import TYPE_CHECKING, List

import numpy as np

from viseron.domains.image_classification import (
    CONFIG_CAMERAS,
    AbstractImageClassification,
    ImageClassificationResult,
)
from viseron.domains.image_classification.const import DOMAIN
from viseron.helpers import calculate_absolute_coords, letterbox_resize

from .const import COMPONENT, CONFIG_IMAGE_CLASSIFICATION

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.post_processor import PostProcessorFrame

    from . import EdgeTPUClassification


def setup(vis: Viseron, config):
    """Set up the edgetpu object_detector domain."""
    for camera_identifier in config[CONFIG_IMAGE_CLASSIFICATION][CONFIG_CAMERAS].keys():
        if (
            config[CONFIG_IMAGE_CLASSIFICATION][CONFIG_CAMERAS][camera_identifier]
            is None
        ):
            config[CONFIG_IMAGE_CLASSIFICATION][CONFIG_CAMERAS][camera_identifier] = {}

        vis.wait_for_camera(
            camera_identifier,
        )
        ImageClassification(vis, COMPONENT, config[DOMAIN], camera_identifier)

    return True


class ImageClassification(AbstractImageClassification):
    """Perform EdgeTPU image classification."""

    def __init__(self, vis, component, config, camera_identifier):
        self._edgetpu: EdgeTPUClassification = vis.data[COMPONENT][
            CONFIG_IMAGE_CLASSIFICATION
        ]
        self._classification_result_queue: Queue[
            List[ImageClassificationResult]
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
    ) -> List[ImageClassificationResult]:
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
            cropped_frame = frame[y1:y2, x1:x2].copy()
            resized_frame = letterbox_resize(
                cropped_frame, self.model_width, self.model_height
            )
            result = self._edgetpu.invoke(
                resized_frame,
                self._camera_identifier,
                self._classification_result_queue,
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
