"""Dlib face recognition."""
import face_recognition


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
