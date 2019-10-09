import logging

import numpy as np
from edgetpu.detection.engine import DetectionEngine

LOGGER = logging.getLogger(__name__)


class ObjectDetection:
    def __init__(self, model, labels, threshold):
        self.threshold = threshold
        self.engine = DetectionEngine(model)
        self.labels = self.read_labels(labels)

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
            processed_objects.append(
                {
                    "label": str(self.labels[obj.label_id]),
                    "confidence": float(obj.score),
                    "height": obj.bounding_box[1][1] - obj.bounding_box[0][1],
                    "width": obj.bounding_box[1][0] - obj.bounding_box[0][0],
                    "relative_x1": obj.bounding_box[0][0],
                    "relative_y1": obj.bounding_box[0][1],
                    "relative_x2": obj.bounding_box[1][0],
                    "relative_y2": obj.bounding_box[1][1],
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
