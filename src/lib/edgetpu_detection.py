import logging

import numpy as np
import tflite_runtime.interpreter as tflite

LOGGER = logging.getLogger(__name__)


class ObjectDetection:
    def __init__(
        self, model, label_path, model_width=None, model_height=None,
    ):
        self.labels = self.read_labels(label_path)
        try:
            self.interpreter = tflite.Interpreter(
                model_path=model,
                experimental_delegates=[tflite.load_delegate("libedgetpu.so.1.0")],
            )
        except ValueError:
            LOGGER.warning("EdgeTPU not found. Detection will run on CPU")
            self.interpreter = tflite.Interpreter(
                model_path="/detectors/models/edgetpu/cpu_model.tflite",
            )
        self.interpreter.allocate_tensors()

        self.tensor_input_details = self.interpreter.get_input_details()
        self.tensor_output_details = self.interpreter.get_output_details()

        if model_width and model_height:
            self._model_width = model_width
            self._model_height = model_height
        else:
            self._model_width = self.tensor_input_details[0]["shape"][1]
            self._model_height = self.tensor_input_details[0]["shape"][2]

    def read_labels(self, file_path):
        with open(file_path, "r") as label_file:
            lines = label_file.readlines()
        labels = {}
        for line in lines:
            pair = line.strip().split(maxsplit=1)
            labels[int(pair[0])] = pair[1].strip()
        return labels

    def pre_process(self, frame):
        # This should be moved to decoder for speed
        frame = frame.get()
        return frame.reshape(1, frame.shape[0], frame.shape[1], frame.shape[2])

    def output_tensor(self, i):
        """Returns output tensor view."""
        tensor = self.interpreter.tensor(
            self.interpreter.get_output_details()[i]["index"]
        )()
        return np.squeeze(tensor)

    def post_process(self, confidence):
        processed_objects = []
        boxes = self.output_tensor(0)
        labels = self.output_tensor(1)
        scores = self.output_tensor(2)
        count = int(self.output_tensor(3))

        for i in range(count):
            if float(scores[i]) > confidence:
                processed_objects.append(
                    {
                        "label": self.labels[int(labels[i])],
                        "confidence": round(float(scores[i]), 3),
                        "height": round(boxes[i][2] - boxes[i][0], 3),
                        "width": round(boxes[i][3] - boxes[i][1], 3),
                        "relative_x1": round(boxes[i][1], 3),
                        "relative_y1": round(boxes[i][0], 3),
                        "relative_x2": round(boxes[i][3], 3),
                        "relative_y2": round(boxes[i][2], 3),
                    }
                )

        return processed_objects

    def return_objects(self, frame):
        tensor = self.pre_process(
            frame["frame"].get_resized_frame(frame["decoder_name"])
        )

        self.interpreter.set_tensor(self.tensor_input_details[0]["index"], tensor)
        self.interpreter.invoke()

        objects = self.post_process(
            frame["camera_config"].object_detection.min_confidence
        )
        return objects

    @property
    def model_width(self):
        return self._model_width

    @property
    def model_height(self):
        return self._model_height
