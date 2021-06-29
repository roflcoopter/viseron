"""dlib face recognition."""
import logging
import math
import os
import os.path
from typing import Any as TypeAny, Dict

import face_recognition
import PIL
from face_recognition.face_recognition_cli import image_files_in_folder
from sklearn import neighbors
from voluptuous import Any, Optional

import viseron.mqtt
from viseron.config import ViseronConfig
from viseron.const import ENV_CUDA_SUPPORTED
from viseron.helpers import calculate_absolute_coords
from viseron.post_processors import PostProcessorFrame
from viseron.post_processors.face_recognition import (
    AbstractFaceRecognition,
    AbstractFaceRecognitionConfig,
    FaceMQTTBinarySensor,
)


def get_default_model() -> str:
    """Return default model."""
    if os.getenv(ENV_CUDA_SUPPORTED) == "true":
        return "cnn"
    return "hog"


SCHEMA = AbstractFaceRecognitionConfig.SCHEMA.extend(
    {
        Optional("model", default=get_default_model()): Any("hog", "cnn"),
    }
)

LOGGER = logging.getLogger(__name__)


class Config(AbstractFaceRecognitionConfig):
    """dlib config."""

    def __init__(
        self,
        processor_config: Dict[str, TypeAny],
    ):
        super().__init__(processor_config)
        self._model = processor_config["model"]

    @property
    def model(self):
        """Return model."""
        return self._model


class Processor(AbstractFaceRecognition):
    """dlib face recognition processor."""

    def __init__(self, config: ViseronConfig, processor_config: Config):
        super().__init__(config, processor_config, LOGGER)
        LOGGER.debug("Initializing dlib")
        self._processor_config: Config = processor_config
        self._classifier, tracked_faces = train(processor_config.face_recognition_path)

        # Create one MQTT binary sensor per tracked face
        self._mqtt_devices = {}
        if viseron.mqtt.MQTT.client:
            for face in list(set(tracked_faces)):
                LOGGER.debug(f"Creating MQTT binary sensor for face {face}")
                self._mqtt_devices[face] = FaceMQTTBinarySensor(config, face)

        LOGGER.debug("dlib initialized")

    def process(self, frame_to_process: PostProcessorFrame):
        """Run face detection."""
        if not self._classifier:
            LOGGER.error(
                "Classifier has not been trained, "
                "make sure the folder structure of faces is correct"
            )
            return

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

        faces = predict(
            cropped_frame, self._classifier, model=self._processor_config.model
        )
        LOGGER.debug(f"Faces found: {faces}")

        for face, coordinates in faces:
            if face != "unknown":
                self.known_face_found(face, coordinates)
            elif self._processor_config.save_unknown_faces:
                self.unknown_face_found(cropped_frame)


def train(
    face_recognition_path,
    # model_dir="model",
    # model_name="trained_faces.clf",
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
    except FileNotFoundError:
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
    Recognizes faces in given image using a trained KNN classifier.

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

    # Find encodings for faces in the test image
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
