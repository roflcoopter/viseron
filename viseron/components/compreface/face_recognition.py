"""CompreFace face recognition."""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import cv2
from compreface import CompreFace
from compreface.collections import FaceCollection
from compreface.service import RecognitionService
from face_recognition.face_recognition_cli import image_files_in_folder

from viseron.domains.camera.shared_frames import SharedFrame
from viseron.domains.face_recognition import AbstractFaceRecognition
from viseron.domains.face_recognition.const import CONFIG_FACE_RECOGNITION_PATH
from viseron.helpers import calculate_absolute_coords

from .const import (
    COMPONENT,
    CONFIG_API_KEY,
    CONFIG_DET_PROB_THRESHOLD,
    CONFIG_FACE_PLUGINS,
    CONFIG_FACE_RECOGNITION,
    CONFIG_HOST,
    CONFIG_LIMIT,
    CONFIG_PORT,
    CONFIG_PREDICTION_COUNT,
    CONFIG_SIMILARITTY_THRESHOLD,
    CONFIG_STATUS,
)

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.object_detector.detected_object import DetectedObject

LOGGER = logging.getLogger(__name__)


def setup(vis: Viseron, config, identifier) -> bool:
    """Set up the CompreFace face_recognition domain."""
    FaceRecognition(vis, config, identifier)

    return True


class FaceRecognition(AbstractFaceRecognition):
    """CompreFace face recognition processor."""

    def __init__(self, vis: Viseron, config, camera_identifier) -> None:
        super().__init__(
            vis, COMPONENT, config[CONFIG_FACE_RECOGNITION], camera_identifier
        )

        options = {
            CONFIG_LIMIT: config[CONFIG_FACE_RECOGNITION][CONFIG_LIMIT],
            CONFIG_DET_PROB_THRESHOLD: config[CONFIG_FACE_RECOGNITION][
                CONFIG_DET_PROB_THRESHOLD
            ],
            CONFIG_PREDICTION_COUNT: config[CONFIG_FACE_RECOGNITION][
                CONFIG_PREDICTION_COUNT
            ],
            CONFIG_STATUS: config[CONFIG_FACE_RECOGNITION][CONFIG_STATUS],
        }
        if config[CONFIG_FACE_RECOGNITION][CONFIG_FACE_PLUGINS]:
            options[CONFIG_FACE_PLUGINS] = config[CONFIG_FACE_RECOGNITION][
                CONFIG_FACE_PLUGINS
            ]

        self._compre_face: CompreFace = CompreFace(
            domain=f"http://{config[CONFIG_FACE_RECOGNITION][CONFIG_HOST]}",
            port=str(config[CONFIG_FACE_RECOGNITION][CONFIG_PORT]),
            options=options,
        )
        self._recognition: RecognitionService = self._compre_face.init_face_recognition(
            config[CONFIG_FACE_RECOGNITION][CONFIG_API_KEY]
        )

    def face_recognition(
        self, shared_frame: SharedFrame, detected_object: DetectedObject
    ) -> None:
        """Perform face recognition."""
        frame = self._camera.shared_frames.get_decoded_frame_rgb(shared_frame)
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

        try:
            detections = self._recognition.recognize(
                cv2.imencode(".jpg", cropped_frame)[1].tobytes(),
            )
        except Exception as error:  # pylint: disable=broad-except
            self._logger.error("Error calling compreface: %s", error, exc_info=True)
            return

        self._logger.debug(f"CompreFace response: {detections}")
        if "result" not in detections:
            return

        for result in detections["result"]:
            subject = result["subjects"][0]
            if subject["similarity"] >= self._config[CONFIG_SIMILARITTY_THRESHOLD]:
                self._logger.debug(f"Face found: {subject}")
                self.known_face_found(
                    subject["subject"],
                    (
                        result["box"]["x_min"] + x1,
                        result["box"]["y_min"] + y1,
                        result["box"]["x_max"] + x2,
                        result["box"]["y_max"] + y2,
                    ),
                    shared_frame,
                    confidence=subject["similarity"],
                    extra_attributes=result,
                )
            else:
                self.unknown_face_found(
                    (
                        result["box"]["x_min"] + x1,
                        result["box"]["y_min"] + y1,
                        result["box"]["x_max"] + x2,
                        result["box"]["y_max"] + y2,
                    ),
                    shared_frame,
                    confidence=subject["similarity"],
                    extra_attributes=result,
                )


class CompreFaceTrain:
    """Train CompreFace to recognize faces."""

    def __init__(self, config) -> None:
        self._config = config

        options = {
            CONFIG_LIMIT: config[CONFIG_FACE_RECOGNITION][CONFIG_LIMIT],
            CONFIG_DET_PROB_THRESHOLD: config[CONFIG_FACE_RECOGNITION][
                CONFIG_DET_PROB_THRESHOLD
            ],
            CONFIG_PREDICTION_COUNT: config[CONFIG_FACE_RECOGNITION][
                CONFIG_PREDICTION_COUNT
            ],
            CONFIG_STATUS: config[CONFIG_FACE_RECOGNITION][CONFIG_STATUS],
        }
        if config[CONFIG_FACE_RECOGNITION][CONFIG_FACE_PLUGINS]:
            options[CONFIG_FACE_PLUGINS] = config[CONFIG_FACE_RECOGNITION][
                CONFIG_FACE_PLUGINS
            ]

        self._compre_face: CompreFace = CompreFace(
            domain=f"http://{config[CONFIG_FACE_RECOGNITION][CONFIG_HOST]}",
            port=str(config[CONFIG_FACE_RECOGNITION][CONFIG_PORT]),
            options=options,
        )
        self._recognition: RecognitionService = self._compre_face.init_face_recognition(
            config[CONFIG_FACE_RECOGNITION][CONFIG_API_KEY]
        )
        self._face_collection: FaceCollection = self._recognition.get_face_collection()

        self.train()

    def train(self) -> None:
        """Train CompreFace to recognize faces."""
        train_dir = self._config[CONFIG_FACE_RECOGNITION][CONFIG_FACE_RECOGNITION_PATH]
        try:
            faces_dirs = os.listdir(train_dir)
        except FileNotFoundError:
            LOGGER.error(
                f"{train_dir} does not exist. "
                "Make sure its created properly. "
                "See the documentation for the proper folder structure"
            )
            return

        for face_dir in faces_dirs:
            if face_dir == "unknown":
                continue

            LOGGER.debug(f"Training face {face_dir}")

            # Loop through each training image for the current person
            try:
                img_paths = image_files_in_folder(os.path.join(train_dir, face_dir))
            except NotADirectoryError as error:
                LOGGER.error(
                    f"{train_dir} can only contain directories. "
                    "Please remove any other files"
                )
                LOGGER.error(error)
                return

            if not img_paths:
                LOGGER.warning(
                    f"No images were found for face {face_dir} "
                    f"in folder {os.path.join(train_dir, face_dir)}. Please provide "
                    f"some images of this person."
                )
                continue

            self._face_collection.delete_all(face_dir)
            for img_path in img_paths:
                face_image = cv2.imencode(".jpg", cv2.imread(img_path))[1].tobytes()
                result = self._face_collection.add(
                    image_path=face_image, subject=face_dir
                )
                LOGGER.debug(f"CompreFace response: {result}")
                if "message" in result:
                    LOGGER.warning(
                        "Image {} not suitable for training: {}".format(
                            img_path, result
                        )
                    )
