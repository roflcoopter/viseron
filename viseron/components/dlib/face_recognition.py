"""dlib face recognition."""
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from viseron.domains.face_recognition import AbstractFaceRecognition
from viseron.domains.face_recognition.const import (
    CONFIG_FACE_RECOGNITION_PATH,
    CONFIG_SAVE_UNKNOWN_FACES,
)
from viseron.helpers import calculate_absolute_coords

from .const import COMPONENT, CONFIG_FACE_RECOGNITION, CONFIG_MODEL
from .predict import predict
from .train import train

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.object_detector.detected_object import DetectedObject
    from viseron.domains.post_processor import PostProcessorFrame

LOGGER = logging.getLogger(__name__)

TRAIN_LOCK = threading.Lock()

CLASSIFIER = "CLASSIFIER"


def setup(vis: Viseron, config, identifier) -> bool:
    """Set up the dlib face_recognition domain."""
    with TRAIN_LOCK:
        if not vis.data[COMPONENT].get(CLASSIFIER, None):
            # We have to train in the domain instead of the component because of a race
            # condition between darknet and dlib. Darknet has to be setup first.
            classifier, _tracked_faces = train(
                config[CONFIG_FACE_RECOGNITION][CONFIG_FACE_RECOGNITION_PATH],
                model=config[CONFIG_FACE_RECOGNITION][CONFIG_MODEL],
            )
            vis.data[COMPONENT][CLASSIFIER] = classifier

    FaceRecognition(vis, config, identifier, vis.data[COMPONENT][CLASSIFIER])

    return True


class FaceRecognition(AbstractFaceRecognition):
    """dlib face recognition processor."""

    def __init__(self, vis: Viseron, config, camera_identifier, classifier) -> None:
        super().__init__(
            vis, COMPONENT, config[CONFIG_FACE_RECOGNITION], camera_identifier
        )
        self._classifier = classifier

    def face_recognition(self, frame, detected_object: DetectedObject) -> None:
        """Perform face recognition."""
        if not self._classifier:
            self._logger.error(
                "Classifier has not been trained, "
                "make sure the folder structure of faces is correct"
            )
            return

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

        faces = predict(
            cropped_frame,
            self._classifier,
            model=self._config[CONFIG_MODEL],
        )
        self._logger.debug(f"Faces found: {faces}")

        for face, coordinates in faces:
            if face != "unknown":
                self.known_face_found(face, coordinates)
            elif self._config[CONFIG_SAVE_UNKNOWN_FACES]:
                self.unknown_face_found(cropped_frame)

    def process(self, post_processor_frame: PostProcessorFrame) -> None:
        """Process received frame."""
        decoded_frame = self._camera.shared_frames.get_decoded_frame_rgb(
            post_processor_frame.shared_frame
        )
        for detected_object in post_processor_frame.filtered_objects:
            self.face_recognition(decoded_frame, detected_object)
