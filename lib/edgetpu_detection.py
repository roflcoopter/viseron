import logging

import numpy as np
from edgetpu.detection.engine import DetectionEngine
from lib.helpers import calculate_relative_coords

LOGGER = logging.getLogger(__name__)


class ObjectDetection:
    def __init__(self, model, labels, threshold, model_res):
        self.threshold = threshold
        self.engine = DetectionEngine(model)
        self.labels = self.read_labels(labels)
        self.model_res = model_res

    def read_labels(self, file_path):
        with open(file_path, "r") as label_file:
            lines = label_file.readlines()
        labels = {}
        for line in lines:
            pair = line.strip().split(maxsplit=1)
            labels[int(pair[0])] = pair[1].strip()
        return labels

    def pre_process(self, frame):
        frame_expanded = np.expand_dims(frame.get(), axis=0)
        return frame_expanded.flatten()

    def post_process(self, objects):
        processed_objects = []
        for obj in objects:
            # Calculate coordinates in the original image
            x1 = int(obj.bounding_box[0][0] * self.model_res[0])
            y1 = int(obj.bounding_box[0][1] * self.model_res[1])
            x2 = int(obj.bounding_box[1][0] * self.model_res[0])
            y2 = int(obj.bounding_box[1][1] * self.model_res[1])
            relative_coords = calculate_relative_coords(
                (x1, y1, x2, y2), self.model_res
            )
            processed_objects.append(
                {
                    "label": str(self.labels[obj.label_id]),
                    "confidence": float(obj.score),
                    "height": int(obj.bounding_box[1][1] - obj.bounding_box[0][1]),
                    "width": int(obj.bounding_box[1][0] - obj.bounding_box[0][0]),
                    "relative_x1": relative_coords[0],
                    "relative_x2": relative_coords[1],
                    "relative_y1": relative_coords[2],
                    "relative_y2": relative_coords[3],
                }
            )
        return processed_objects

    def return_objects(self, frame):
        tensor = self.pre_process(frame)

        detected_objects = self.engine.DetectWithInputTensor(
            tensor, threshold=self.threshold, top_k=3
        )

        objects = self.post_process(detected_objects)
        # LOGGER.info(self.engine.get_inference_time())
        return objects
