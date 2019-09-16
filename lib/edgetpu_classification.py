import logging
import numpy as np
from edgetpu.classification.engine import ClassificationEngine

LOGGER = logging.getLogger(__name__)


class ObjectClassification(object):
    def __init__(self, model, labels, threshold, camera_res):
        self.threshold = threshold
        self.engine = ClassificationEngine(model)
        self.labels = self.read_labels(labels)
        self.camera_res = camera_res

    def read_labels(self, file_path):
        with open(file_path, 'r') as f:
            lines = f.readlines()
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
        for label_id, score in objects:
            processed_objects.append({
                "label": str(self.labels[label_id]),
                "confidence": float(score)
            })
        return processed_objects

    def return_objects(self, frame):
        tensor = self.pre_process(frame)

        detected_objects = self.engine.ClassifyWithInputTensor(
            tensor,
            threshold=self.threshold,
            top_k=3)

        objects = self.post_process(detected_objects)
        # LOGGER.info(self.engine.get_inference_time())
        return objects
