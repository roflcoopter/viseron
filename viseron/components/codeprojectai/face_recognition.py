"""CodeProject.AI face recognition."""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import codeprojectai.core as cpai
import cv2
import requests
from face_recognition.face_recognition_cli import image_files_in_folder

from viseron.domains.face_recognition import AbstractFaceRecognition
from viseron.domains.face_recognition.const import (
    CONFIG_FACE_RECOGNITION_PATH,
    CONFIG_SAVE_UNKNOWN_FACES,
)
from viseron.helpers import calculate_absolute_coords, letterbox_resize

from .const import (
    COMPONENT,
    CONFIG_FACE_RECOGNITION,
    CONFIG_HOST,
    CONFIG_MIN_CONFIDENCE,
    CONFIG_PORT,
    CONFIG_TIMEOUT,
)

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.object_detector.detected_object import DetectedObject
    from viseron.domains.post_processor import PostProcessorFrame

LOGGER = logging.getLogger(__name__)


def setup(vis: Viseron, config, identifier) -> bool:
    """Set up the codeprojectai face_recognition domain."""
    FaceRecognition(vis, config, identifier)

    return True


class FaceRecognition(AbstractFaceRecognition):
    """CodeProject.AI face recognition processor."""

    def __init__(self, vis: Viseron, config, camera_identifier) -> None:
        super().__init__(
            vis, COMPONENT, config[CONFIG_FACE_RECOGNITION], camera_identifier
        )

        self._cpai_config = config
        self._cpai = CodeProjectAIFace(
            ip=config[CONFIG_HOST],
            port=config[CONFIG_PORT],
            timeout=config[CONFIG_TIMEOUT],
            min_confidence=config[CONFIG_FACE_RECOGNITION][CONFIG_MIN_CONFIDENCE],
        )

    def face_recognition(self, frame, detected_object: DetectedObject) -> None:
        """Perform face recognition."""
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
        width, height, _ = cropped_frame.shape
        max_dimension = max(width, height)
        cropped_frame = letterbox_resize(cropped_frame, max_dimension, max_dimension)

        try:
            result = self._cpai.recognize(
                cv2.imencode(".jpg", cropped_frame)[1].tobytes()
            )
        except cpai.CodeProjectAIException as error:
            self._logger.error("Error calling CodeProject.AI: %s", error)
            return

        self._logger.debug("Face recognition result: %s", result)
        if not result["success"]:
            return

        for detection in result["predictions"]:
            if detection["userid"] != "unknown":
                self._logger.debug(f"Face found: {detection}")
                self.known_face_found(
                    detection["userid"],
                    (
                        detection["x_min"],
                        detection["y_min"],
                        detection["x_max"],
                        detection["y_max"],
                    ),
                    confidence=detection["confidence"],
                )
            elif self._config[CONFIG_SAVE_UNKNOWN_FACES]:
                self.unknown_face_found(cropped_frame)

    def process(self, post_processor_frame: PostProcessorFrame) -> None:
        """Process received frame."""
        decoded_frame = self._camera.shared_frames.get_decoded_frame_rgb(
            post_processor_frame.shared_frame
        )
        for detected_object in post_processor_frame.filtered_objects:
            self.face_recognition(decoded_frame, detected_object)


class CodeProjectAITrain:
    """Train CodeProject.AI to recognize faces."""

    def __init__(self, config) -> None:
        self._config = config
        self._cpai = CodeProjectAIFace(
            ip=config[CONFIG_HOST],
            port=config[CONFIG_PORT],
            timeout=config[CONFIG_TIMEOUT],
            min_confidence=config[CONFIG_FACE_RECOGNITION][CONFIG_MIN_CONFIDENCE],
        )
        self.train()

    def train(self) -> None:
        """Train CodeProject.AI to recognize faces."""
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

            self._cpai.delete_face(face_dir)
            for img_path in img_paths:
                face_image = cv2.imread(img_path)
                width, height, _ = face_image.shape
                max_dimension = max(width, height)
                face_image = letterbox_resize(face_image, max_dimension, max_dimension)
                face_image = cv2.imencode(".jpg", face_image)[1].tobytes()
                detections = self._cpai.detect(face_image)
                LOGGER.debug("Face detection result: %s", detections)
                if len(detections) != 1:
                    # Skip image if amount of people !=1
                    LOGGER.warning(
                        "Image {} not suitable for training: {}".format(
                            img_path,
                            "Didn't find a face"
                            if len(detections) < 1
                            else "Found more than one face",
                        )
                    )
                else:
                    self._cpai.register(face_dir, face_image)


HTTP_OK = 200
BAD_URL = 404


class CodeProjectAIFace(cpai.CodeProjectAIFace):
    """Custom CodeProjectAIFace to add list and delete function."""

    @staticmethod
    def post_request(url, timeout=None, data: dict | None = None):
        """Send post req to CodeProject.AI."""
        try:
            response = requests.post(url, data=data, timeout=timeout)
        except requests.exceptions.Timeout:
            raise cpai.CodeProjectAIException(  # pylint: disable=raise-missing-from
                "Timeout connecting to CodeProject.AI, "
                f"the current timeout is {timeout} "
                "seconds, try increasing this value"
            )
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.MissingSchema,
        ) as exc:
            raise cpai.CodeProjectAIException(
                f"CodeProject.AI connection error, check your IP and port: {exc}"
            )

        if response.status_code == HTTP_OK:
            return response.json()
        if response.status_code == BAD_URL:
            raise cpai.CodeProjectAIException(
                f"Bad url supplied, url {url} raised error {BAD_URL}"
            )
        raise cpai.CodeProjectAIException(
            f"Error from CodeProject.AI request, status code: {response.status_code}"
        )

    def list_faces(self):
        """List taught faces."""
        response = self.post_request(
            url=self._url_base + "/face/list",
            timeout=self.timeout,
        )
        del response["success"]
        return response

    def delete_face(self, face):
        """Delete a taught faces."""
        response = self.post_request(
            url=self._url_base + "/face/delete",
            timeout=self.timeout,
            data={"userid": face},
        )
        del response["success"]
        return response

    def recognize(self, image_bytes: bytes):
        """Process image_bytes, performing recognition."""
        response = cpai.process_image(
            url=self._url_recognize,
            image_bytes=image_bytes,
            min_confidence=self.min_confidence,
            timeout=self.timeout,
        )

        return response
