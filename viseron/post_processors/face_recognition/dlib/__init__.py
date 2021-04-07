import datetime
import logging
import math
import os
import os.path
from threading import Timer
from uuid import uuid4

from voluptuous import All, Any, Coerce, Optional, Range

import cv2
import face_recognition
import PIL
from viseron.const import ENV_CUDA_SUPPORTED
from face_recognition.face_recognition_cli import image_files_in_folder
from viseron.config import ViseronConfig
from viseron.helpers import calculate_absolute_coords, slugify
from viseron.mqtt.binary_sensor import MQTTBinarySensor
from viseron.post_processors import PostProcessorConfig
from viseron.post_processors.schema import SCHEMA as BASE_SCHEMA
from sklearn import neighbors

from .defaults import (
    EXPIRE_AFTER,
    FACE_RECOGNITION_PATH,
    SAVE_UNKNOWN_FACES,
    UNKNOWN_FACES_PATH,
)


def get_default_model() -> str:
    if os.getenv(ENV_CUDA_SUPPORTED) == "true":
        return "cnn"
    return "hog"


SCHEMA = BASE_SCHEMA.extend(
    {
        Optional("face_recognition_path", default=FACE_RECOGNITION_PATH): str,
        Optional("save_unknown_faces", default=SAVE_UNKNOWN_FACES): bool,
        Optional("unknown_faces_path", default=UNKNOWN_FACES_PATH): str,
        Optional("expire_after", default=EXPIRE_AFTER): All(
            Any(All(int, Range(min=0)), All(float, Range(min=0.0))), Coerce(float)
        ),
        Optional("model", default=get_default_model()): Any("hog", "cnn"),
    }
)

LOGGER = logging.getLogger(__name__)


class Config(PostProcessorConfig):
    def __init__(self, post_processors_config, processor_config):
        super().__init__(post_processors_config, processor_config)
        self._face_recognition_path = processor_config["face_recognition_path"]
        self._save_unknown_faces = processor_config["save_unknown_faces"]
        self._unknown_faces_path = processor_config["unknown_faces_path"]
        self._expire_after = processor_config["expire_after"]
        self._model = processor_config["model"]

    @property
    def face_recognition_path(self):
        return self._face_recognition_path

    @property
    def save_unknown_faces(self):
        return self._save_unknown_faces

    @property
    def unknown_faces_path(self):
        return self._unknown_faces_path

    @property
    def expire_after(self):
        return self._expire_after

    @property
    def model(self):
        return self._model


class Processor:
    def __init__(self, config: ViseronConfig, processor_config: Config, mqtt_queue):
        if getattr(processor_config.logging, "level", None):
            LOGGER.setLevel(processor_config.logging.level)
        LOGGER.debug("Initializing dlib")
        self._processor_config = processor_config

        self._faces: dict = {}
        self._classifier, tracked_faces = train(processor_config.face_recognition_path)

        # Create one MQTT binary sensor per tracked face
        self._mqtt_devices = {}
        if mqtt_queue:
            for face in list(set(tracked_faces)):
                LOGGER.debug(f"Creating MQTT binary sensor for face {face}")
                self._mqtt_devices[face] = FaceMQTTBinarySensor(
                    config, mqtt_queue, face
                )

        if processor_config.save_unknown_faces:
            create_directory(processor_config.unknown_faces_path)

        LOGGER.debug("dlib initialized")

    def known_face_found(self, face, coordinates):
        # Cancel the expiry timer if face has already been detected
        if self._faces.get(face, None):
            self._faces[face]["timer"].cancel()

        self._mqtt_devices[face].publish(True)

        # Adds a detected face and schedules an expiry timer
        self._faces[face] = {
            "coordinates": coordinates,
            "timer": Timer(
                self._processor_config.expire_after, self.expire_face, [face]
            ),
        }
        self._faces[face]["timer"].start()

    def unknown_face_found(self, frame):
        unique_id = f"{datetime.datetime.now().strftime('%H:%M:%S-')}{str(uuid4())}.jpg"
        file_name = os.path.join(self._processor_config.unknown_faces_path, unique_id)
        LOGGER.debug(f"Unknown face found, saving to {file_name}")

        if not cv2.imwrite(file_name, frame):
            LOGGER.error("Failed saving unknown face image to disk")

    def process(self, camera_config, frame, obj, zone):
        if not self._classifier:
            LOGGER.error(
                "Classifier has not been trained, "
                "make sure the folder structure of faces is correct"
            )
            return

        height, width, _ = frame.decoded_frame_mat_rgb.shape
        x1, y1, x2, y2 = calculate_absolute_coords(
            (
                obj.rel_x1,
                obj.rel_y1,
                obj.rel_x2,
                obj.rel_y2,
            ),
            (width, height),
        )
        cropped_frame = frame.decoded_frame_mat_rgb[y1:y2, x1:x2].copy()

        faces = predict(
            cropped_frame, self._classifier, model=self._processor_config.model
        )
        LOGGER.debug(f"Faces found: {faces}")

        for face, coordinates in faces:
            if face != "unknown":
                self.known_face_found(face, coordinates)
            elif self._processor_config.save_unknown_faces:
                self.unknown_face_found(cropped_frame)

    def expire_face(self, face):
        LOGGER.debug(f"Expiring face {face}")
        self._mqtt_devices[face].publish(False)
        del self._faces[face]

    def on_connect(self, client):
        for device in self._mqtt_devices.values():
            device.on_connect(client)


def create_directory(path):
    try:
        if not os.path.isdir(path):
            LOGGER.debug(f"Creating folder {path}")
            os.makedirs(path)
    except FileExistsError:
        pass


def train(
    face_recognition_path,
    model_dir="model",
    model_name="trained_faces.clf",
    n_neighbors=None,
):
    """
    Trains a k-nearest neighbors classifier for face recognition.

    :param face_recognition_path: directory that contains
        a sub-directory for each known person.
        Default Structure:
            /config/
            |── face_recognition/
            |   |── faces/
            |   |   ├── person1/
            |   |   │   ├── someimage1.jpeg
            |   |   │   ├── someimage2.png
            |   |   │   ├── someimage3.jpeg
            |   |   │   ├── ...
            |   |   ├── person2/
            |   |   │   ├── someimage1.jpeg
            |   |   │   ├── someimage2.png
            |   |   └── ...

    :param model_dir: (optional) path to save model on disk
    :param model_name: (optional) filename of saved model
    :param n_neighbors: (optional) number of neighbors to weigh in classification.
        Chosen automatically if not specified
    :return: returns knn classifier that was trained on the given data.
    """
    LOGGER.debug("Training faces...")

    face_encodings = []
    face_names = []

    # Loop through each person in the training set
    train_dir = os.path.join(face_recognition_path, "faces")
    try:
        faces_dirs = os.listdir(train_dir)
    except FileNotFoundError as error:
        LOGGER.error(
            f"{train_dir} does not exist. "
            "Make sure its created properly. "
            "See the documentation for the proper folder structure"
        )
        return None, []

    if not faces_dirs:
        LOGGER.warning(
            f"face_recognition is configured, "
            f"but no subfolders in {train_dir} could be found"
        )
        return None, []

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

        if not img_paths:
            LOGGER.warning(
                f"No images were found for face {face_dir} "
                f"in folder {os.path.join(train_dir, face_dir)}. Please provide "
                f"some images of this person."
            )
            continue

        for img_path in img_paths:
            try:
                image = face_recognition.load_image_file(img_path)
            except PIL.UnidentifiedImageError as error:
                LOGGER.error(f"Error loading image: {error}")
                continue

            face_bounding_boxes = face_recognition.face_locations(image)

            if len(face_bounding_boxes) != 1:
                # Skip image if amount of people !=1
                LOGGER.warning(
                    "Image {} not suitable for training: {}".format(
                        img_path,
                        "Didn't find a face"
                        if len(face_bounding_boxes) < 1
                        else "Found more than one face",
                    )
                )
            else:
                # Add face encoding for current image to the training set
                face_encodings.append(
                    face_recognition.face_encodings(
                        image, known_face_locations=face_bounding_boxes
                    )[0]
                )
                face_names.append(face_dir)

    if not face_encodings:
        LOGGER.error(f"No faces found for training in {train_dir}")
        return None, []

    # model_path = os.path.join(train_dir, model_dir)

    # try:
    #     os.makedirs(model_path)
    #     LOGGER.debug(f"Model dir missing, creating {model_path}")
    # except FileExistsError:
    #     pass

    # Determine how many neighbors to use for weighting in the KNN classifier
    if n_neighbors is None:
        n_neighbors = int(round(math.sqrt(len(face_encodings))))

    # Create and train the KNN classifier
    knn_clf = neighbors.KNeighborsClassifier(
        n_neighbors=n_neighbors, algorithm="ball_tree", weights="distance"
    )
    knn_clf.fit(face_encodings, face_names)

    # # Save the trained KNN classifier
    # with open(os.path.join(model_path, model_name), "wb") as model_file:
    #     pickle.dump(knn_clf, model_file)

    LOGGER.debug("Training complete")
    return knn_clf, face_names


def predict(frame, knn_clf, model="hog", distance_threshold=0.6):
    """
    Recognizes faces in given image using a trained KNN classifier

    :param frame: frame to run prediction on
    :param knn_clf: (optional) a knn classifier object.
    :param model: Which face detection model to use.
        "hog" is less accurate but faster on CPUs.
        "cnn" is a more accurate deep-learning model which is
        GPU/CUDA accelerated (if available). The default is “hog”.
    :param distance_threshold: (optional) distance threshold for face classification.
        The chance of classifying an unknown person as a known one
        increases with this value.
    :return: a list of names and face locations for the recognized faces in the image:
        [(name, bounding box), ...].
        For faces of unrecognized persons, the name 'unknown' will be returned.
    """

    # Load image file and find face locations
    face_locations = face_recognition.face_locations(frame, model=model)

    # If no faces are found in the image, return an empty result.
    if len(face_locations) == 0:
        return []

    # Find encodings for faces in the test iamge
    faces_encodings = face_recognition.face_encodings(
        frame, known_face_locations=face_locations
    )

    # Use the KNN model to find the best matches
    closest_distances = knn_clf.kneighbors(faces_encodings, n_neighbors=1)
    are_matches = [
        closest_distances[0][i][0] <= distance_threshold
        for i in range(len(face_locations))
    ]

    # Predict classes and remove classifications that aren't within the threshold
    return [
        (pred, loc) if rec else ("unknown", loc)
        for pred, loc, rec in zip(
            knn_clf.predict(faces_encodings), face_locations, are_matches
        )
    ]


class FaceMQTTBinarySensor(MQTTBinarySensor):
    def __init__(self, config, mqtt_queue, face):
        self._config = config
        self._mqtt_queue = mqtt_queue
        self._name = f"{config.mqtt.client_id} Face detected {face}"
        self._friendly_name = f"Face detected {face}"
        self._device_name = config.mqtt.client_id
        self._unique_id = self._name
        self._node_id = slugify(config.mqtt.client_id)
        self._object_id = f"face_detected_{slugify(face)}"

    @property
    def state_topic(self):
        return f"{self._config.mqtt.client_id}/binary_sensor/{self.object_id}/state"
