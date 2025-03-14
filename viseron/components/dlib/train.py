"""Train dlib."""
import logging
import math
import os

import face_recognition
import PIL
from sklearn import neighbors

from viseron.helpers import get_image_files_in_folder

LOGGER = logging.getLogger(__name__)


def train(
    face_recognition_path,
    model="hog",
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
    try:
        faces_dirs = os.listdir(face_recognition_path)
    except FileNotFoundError:
        LOGGER.error(
            f"{face_recognition_path} does not exist. "
            "Make sure its created properly. "
            "See the documentation for the proper folder structure"
        )
        return None, []

    if not faces_dirs:
        LOGGER.warning(
            f"face_recognition is configured, "
            f"but no subfolders in {face_recognition_path} could be found"
        )
        return None, []

    for face_dir in faces_dirs:
        if face_dir == "unknown":
            continue

        LOGGER.debug(f"Training face {face_dir}")

        # Loop through each training image for the current person
        try:
            img_paths = get_image_files_in_folder(
                os.path.join(face_recognition_path, face_dir)
            )
        except NotADirectoryError as error:
            LOGGER.error(
                f"{face_recognition_path} can only contain directories. "
                "Please remove any other files"
            )
            LOGGER.error(error)

        if not img_paths:
            LOGGER.warning(
                f"No images were found for face {face_dir} "
                f"in folder {os.path.join(face_recognition_path, face_dir)}. "
                f"Please provide some images of this person."
            )
            continue

        for img_path in img_paths:
            try:
                image = face_recognition.load_image_file(img_path)
            except PIL.UnidentifiedImageError as error:
                LOGGER.error(f"Error loading image: {error}")
                continue

            face_bounding_boxes = face_recognition.face_locations(image, model=model)

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
        LOGGER.error(f"No faces found for training in {face_recognition_path}")
        return None, []

    # model_path = os.path.join(face_recognition_path, model_dir)

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
