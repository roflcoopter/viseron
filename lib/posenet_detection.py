import logging

from lib.helpers import calculate_relative_coords
from lib.pose_engine import PoseEngine

LOGGER = logging.getLogger(__name__)

EDGES = (
    ("nose", "left eye"),
    ("nose", "right eye"),
    ("nose", "left ear"),
    ("nose", "right ear"),
    ("left ear", "left eye"),
    ("right ear", "right eye"),
    ("left eye", "right eye"),
    ("left shoulder", "right shoulder"),
    ("left shoulder", "left elbow"),
    ("left shoulder", "left hip"),
    ("right shoulder", "right elbow"),
    ("right shoulder", "right hip"),
    ("left elbow", "left wrist"),
    ("right elbow", "right wrist"),
    ("left hip", "right hip"),
    ("left hip", "left knee"),
    ("right hip", "right knee"),
    ("left knee", "left ankle"),
    ("right knee", "right ankle"),
)


class ObjectDetection(object):
    def __init__(self, model, threshold, model_res):
        self.engine = PoseEngine(model)
        self.threshold = threshold
        self.model_res = model_res

    def pre_process(self, frame):
        return frame.get()

    def post_process(self, poses, threshold=0.2):
        x_coords = []
        y_coords = []
        processed_objects = []
        for pose in poses:
            if pose.score < self.threshold:
                continue
            for label, keypoint in pose.keypoints.items():
                if keypoint.score < threshold:
                    continue
                x_coords.append(int(keypoint.yx[1]))
                y_coords.append(int(keypoint.yx[0]))

            if x_coords and y_coords:
                x1 = int(min(x_coords))
                y1 = int(min(y_coords))
                x2 = int(max(x_coords))
                y2 = int(max(y_coords))
                relative_coords = calculate_relative_coords(
                    (x1, y1, x2, y2), self.model_res
                )
                processed_objects.append(
                    {
                        "label": "person",
                        "confidence": float(pose.score),
                        "height": relative_coords[3] - relative_coords[2],
                        "width": relative_coords[1] - relative_coords[0],
                        "relative_x1": relative_coords[0],
                        "relative_x2": relative_coords[1],
                        "relative_y1": relative_coords[2],
                        "relative_y2": relative_coords[3],
                    }
                )
        return processed_objects

    def return_objects(self, frame):
        poses, inference_time = self.engine.DetectPosesInImage(self.pre_process(frame))
        # LOGGER.info(inference_time)
        return self.post_process(poses)
