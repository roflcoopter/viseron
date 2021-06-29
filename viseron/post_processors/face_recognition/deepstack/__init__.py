"""DeepStack face recognition."""
import logging
import os
from typing import Any, Dict

import cv2
import deepstack.core as ds
import requests
import voluptuous as vol
from face_recognition.face_recognition_cli import image_files_in_folder

import viseron.mqtt
from viseron.config import ViseronConfig
from viseron.helpers import calculate_absolute_coords
from viseron.post_processors import PostProcessorFrame
from viseron.post_processors.face_recognition import (
    AbstractFaceRecognition,
    AbstractFaceRecognitionConfig,
    FaceMQTTBinarySensor,
)

from .defaults import TIMEOUT

SCHEMA = AbstractFaceRecognitionConfig.SCHEMA.extend(
    {
        vol.Required("host"): str,
        vol.Required("port"): int,
        vol.Optional("api_key", default=None): vol.Maybe(str),
        vol.Optional("timeout", default=TIMEOUT): int,
        vol.Optional("train", default=True): bool,
        vol.Optional("min_confidence", default=0.5): vol.All(
            vol.Any(0, 1, vol.All(float, vol.Range(min=0.0, max=1.0))),
            vol.Coerce(float),
        ),
    }
)

LOGGER = logging.getLogger(__name__)


class Config(AbstractFaceRecognitionConfig):
    """DeepStack face recognition config."""

    def __init__(
        self,
        processor_config: Dict[str, Any],
    ):
        super().__init__(processor_config)
        self._host = processor_config["host"]
        self._port = processor_config["port"]
        self._api_key = processor_config["api_key"]
        self._timeout = processor_config["timeout"]
        self._train = processor_config["train"]
        self._min_confidence = processor_config["min_confidence"]

    @property
    def host(self) -> str:
        """Return Deepstack host."""
        return self._host

    @property
    def port(self) -> int:
        """Return Deepstack port."""
        return self._port

    @property
    def api_key(self) -> str:
        """Return API key."""
        return self._api_key

    @property
    def timeout(self) -> int:
        """Return timeout."""
        return self._timeout

    @property
    def train(self) -> int:
        """Return if faces should be trained."""
        return self._train

    @property
    def min_confidence(self) -> float:
        """Return if faces should be trained."""
        return self._min_confidence


class Processor(AbstractFaceRecognition):
    """DeepSTack face recognition processor."""

    def __init__(self, config: ViseronConfig, processor_config: Config):
        super().__init__(config, processor_config, LOGGER)
        self._ds = DeepstackFace(
            ip=processor_config.host,
            port=processor_config.port,
            api_key=processor_config.api_key,
            timeout=processor_config.timeout,
            min_confidence=processor_config.min_confidence,
        )
        if processor_config.train:
            self.train()

        trained_faces = self._ds.list_faces()
        # Create one MQTT binary sensor per tracked face
        self._mqtt_devices = {}
        if viseron.mqtt.MQTT.client:
            for face in trained_faces["faces"]:
                LOGGER.debug(f"Creating MQTT binary sensor for face {face}")
                self._mqtt_devices[face] = FaceMQTTBinarySensor(config, face)

    def process(self, frame_to_process: PostProcessorFrame):
        """Process received frame."""
        height, width, _ = frame_to_process.frame.decoded_frame_mat_rgb.shape
        x1, y1, x2, y2 = calculate_absolute_coords(
            (
                frame_to_process.detected_object.rel_x1,
                frame_to_process.detected_object.rel_y1,
                frame_to_process.detected_object.rel_x2,
                frame_to_process.detected_object.rel_y2,
            ),
            (width, height),
        )
        cropped_frame = frame_to_process.frame.decoded_frame_mat_rgb[
            y1:y2, x1:x2
        ].copy()

        try:
            detections = self._ds.recognize(
                cv2.imencode(".jpg", cropped_frame)[1].tobytes()
            )
        except ds.DeepstackException as error:
            LOGGER.error("Error calling deepstack: %s", error)
        for detection in detections:
            if detection["userid"] != "unknown":
                LOGGER.debug("Face found: {}".format(detection))
                self.known_face_found(
                    detection["userid"],
                    (
                        detection["x_min"],
                        detection["y_min"],
                        detection["x_max"],
                        detection["y_max"],
                    ),
                )
            elif self._processor_config.save_unknown_faces:
                self.unknown_face_found(cropped_frame)

    def train(self):
        """Train DeepStack to recognize faces."""
        train_dir = os.path.join(self._processor_config.face_recognition_path, "faces")
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
