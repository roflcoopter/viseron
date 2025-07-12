"""DeepStack face recognition."""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import cv2
import deepstack.core as ds
import numpy as np
import requests

from viseron.domains.face_recognition import AbstractFaceRecognition
from viseron.domains.face_recognition.const import CONFIG_FACE_RECOGNITION_PATH
from viseron.helpers import calculate_absolute_coords, get_image_files_in_folder

from .const import (
    COMPONENT,
    CONFIG_API_KEY,
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
    """Set up the deepstack face_recognition domain."""
    FaceRecognition(vis, config, identifier)

    return True


class FaceRecognition(AbstractFaceRecognition):
    """DeepSTack face recognition processor."""

    def __init__(self, vis: Viseron, config, camera_identifier) -> None:
        super().__init__(
            vis, COMPONENT, config[CONFIG_FACE_RECOGNITION], camera_identifier
        )

        self._ds_config = config
        self._ds = DeepstackFace(
            ip=config[CONFIG_HOST],
            port=config[CONFIG_PORT],
            api_key=config[CONFIG_API_KEY],
            timeout=config[CONFIG_TIMEOUT],
            min_confidence=config[CONFIG_FACE_RECOGNITION][CONFIG_MIN_CONFIDENCE],
        )

    def preprocess(self, frame) -> np.ndarray:
        """Preprocess frame."""
        return frame

    def face_recognition(
        self, post_processor_frame: PostProcessorFrame, detected_object: DetectedObject
    ) -> None:
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
        cropped_frame = post_processor_frame.frame[y1:y2, x1:x2].copy()

        try:
            detections = self._ds.recognize(
                cv2.imencode(".jpg", cropped_frame)[1].tobytes()
            )
        except ds.DeepstackException as error:
            self._logger.error("Error calling deepstack: %s", error)

        for detection in detections:
            if detection["userid"] != "unknown":
                self._logger.debug(f"Face found: {detection}")
                self.known_face_found(
                    detection["userid"],
                    (
                        detection["x_min"] + x1,
                        detection["y_min"] + y1,
                        detection["x_max"] + x2,
                        detection["y_max"] + y2,
                    ),
                    post_processor_frame.shared_frame,
                    confidence=detection["confidence"],
                )
            else:
                self.unknown_face_found(
                    (
                        detection["x_min"] + x1,
                        detection["y_min"] + y1,
                        detection["x_max"] + x2,
                        detection["y_max"] + y2,
                    ),
                    post_processor_frame.shared_frame,
                    confidence=detection["confidence"],
                )


class DeepstackTrain:
    """Train DeepStack to recognize faces."""

    def __init__(self, config) -> None:
        self._config = config
        self._ds = DeepstackFace(
            ip=config[CONFIG_HOST],
            port=config[CONFIG_PORT],
            api_key=config[CONFIG_API_KEY],
            timeout=config[CONFIG_TIMEOUT],
            min_confidence=config[CONFIG_FACE_RECOGNITION][CONFIG_MIN_CONFIDENCE],
        )
        self.train()

    def train(self) -> None:
        """Train DeepStack to recognize faces."""
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
                img_paths = get_image_files_in_folder(os.path.join(train_dir, face_dir))
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

            self._ds.delete_face(face_dir)
            for img_path in img_paths:
                face_image = cv2.imencode(".jpg", cv2.imread(img_path))[1].tobytes()
                detections = self._ds.detect(face_image)
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
                    self._ds.register(face_dir, face_image)


HTTP_OK = 200
BAD_URL = 404


class DeepstackFace(ds.DeepstackFace):
    """Custom DeepstackFace to add list and delete function."""

    # pylint: disable=dangerous-default-value
    @staticmethod
    def post_request(url, api_key=None, timeout=None, data: dict = {}):
        """Send post req to DeepStack."""
        data["api_key"] = api_key
        try:
            response = requests.post(url, data=data, timeout=timeout)
        except requests.exceptions.Timeout:
            raise ds.DeepstackException(  # pylint: disable=raise-missing-from
                f"Timeout connecting to Deepstack, the current timeout is {timeout} "
                "seconds, try increasing this value"
            )
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.MissingSchema,
        ) as exc:
            raise ds.DeepstackException(
                f"Deepstack connection error, check your IP and port: {exc}"
            )

        if response.status_code == HTTP_OK:
            return response.json()
        if response.status_code == BAD_URL:
            raise ds.DeepstackException(
                f"Bad url supplied, url {url} raised error {BAD_URL}"
            )
        raise ds.DeepstackException(
            f"Error from Deepstack request, status code: {response.status_code}"
        )

    def list_faces(self):
        """List taught faces."""
        response = self.post_request(
            url=self._url_base + "/face/list",
            api_key=self._api_key,
            timeout=self._timeout,
        )
        del response["success"]
        return response

    def delete_face(self, face):
        """Delete a taught faces."""
        response = self.post_request(
            url=self._url_base + "/face/delete",
            api_key=self._api_key,
            timeout=self._timeout,
            data={"userid": face},
        )
        del response["success"]
        return response


# pylint enable
