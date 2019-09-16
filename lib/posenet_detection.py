import logging
from lib.pose_engine import PoseEngine

LOGGER = logging.getLogger(__name__)

EDGES = (
    ('nose', 'left eye'),
    ('nose', 'right eye'),
    ('nose', 'left ear'),
    ('nose', 'right ear'),
    ('left ear', 'left eye'),
    ('right ear', 'right eye'),
    ('left eye', 'right eye'),
    ('left shoulder', 'right shoulder'),
    ('left shoulder', 'left elbow'),
    ('left shoulder', 'left hip'),
    ('right shoulder', 'right elbow'),
    ('right shoulder', 'right hip'),
    ('left elbow', 'left wrist'),
    ('right elbow', 'right wrist'),
    ('left hip', 'right hip'),
    ('left hip', 'left knee'),
    ('right hip', 'right knee'),
    ('left knee', 'left ankle'),
    ('right knee', 'right ankle'),
)


class ObjectDetection(object):
    def __init__(self, model, threshold, model_res, camera_res):
        self.engine = PoseEngine(model)
        self.threshold = threshold

        self.x_scale = camera_res[0] / model_res[0]
        self.y_scale = camera_res[1] / model_res[1]

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
                x1 = int(min(x_coords) * self.x_scale)
                y1 = int(min(y_coords) * self.y_scale)
                x2 = int(max(x_coords) * self.x_scale)
                y2 = int(max(y_coords) * self.y_scale)
                processed_objects.append({
                    "label": "person",
                    "confidence": float(pose.score),
                    "height": y2 - y1,
                    "width": x2 - x1,
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "unscaled_x1": int(min(x_coords)),
                    "unscaled_y1": int(min(y_coords)),
                    "unscaled_x2": int(max(x_coords)),
                    "unscaled_y2": int(max(y_coords))
                })
        return processed_objects

    def return_objects(self, frame):
        poses, inference_time = self.engine.DetectPosesInImage(self.pre_process(frame))
        #LOGGER.info(inference_time)
        return self.post_process(poses)
