"""Runs EdgeTPU detection.

This script is spawned as a subprocess by the EdgeTPU component.
It is responsible for running the EdgeTPU model and sending the results back to the
main process using BaseManager queues.

The reason for running it in a separate shell and not using multiprocessing is that
the EdgeTPU library is only compatible with Python 3.9 and the main process is running
a newer version of Python.
"""
import argparse
import logging
import sys
from abc import abstractmethod

import numpy as np
import tflite_runtime.interpreter as tflite
from pycoral.adapters import classify, common, detect
from pycoral.utils.edgetpu import make_interpreter

from manager import connect

LOGGER = logging.getLogger(__name__)


class MakeInterpreterError(Exception):
    """Error raised on all failures to make interpreter."""


class EdgeTPU:
    """EdgeTPU interface."""

    def __init__(self, device: str, model: str):
        self._device = device
        self.interpreter = self.make_interpreter(
            device=device,
            model=model,
        )
        LOGGER.debug("EdgeTPU initialized")

    def make_interpreter(self, device, model):
        """Make interpreter."""
        LOGGER.debug(f"Loading interpreter with device {device}, model {model}")
        if device == "cpu":
            interpreter = tflite.Interpreter(
                model_path=model,
            )
        else:
            try:
                interpreter = make_interpreter(
                    model,
                    device=self._device,
                )
            except Exception as error:
                LOGGER.error(f"Error when trying to load EdgeTPU: {error}")
                raise MakeInterpreterError from error
        interpreter.allocate_tensors()
        return interpreter

    def get_model_size(self) -> tuple:
        """Get model size."""
        tensor_input_details = self.interpreter.get_input_details()
        model_width = tensor_input_details[0]["shape"][1]
        model_height = tensor_input_details[0]["shape"][2]
        return model_width, model_height

    @abstractmethod
    def work_input(self, item):
        """Perform work on input."""


class EdgeTPUDetection(EdgeTPU):
    """EdgeTPU object detector interface."""

    def work_input(self, item):
        """Perform object detection."""
        common.set_input(self.interpreter, item["frame"])
        self.interpreter.invoke()
        processed_objects = []
        objs = detect.get_objects(self.interpreter, 0.1)
        for obj in objs:
            processed_objects.append(
                {
                    "label": obj.id,
                    "score": float(obj.score),
                    "bbox": {
                        "xmin": obj.bbox.xmin,
                        "ymin": obj.bbox.ymin,
                        "xmax": obj.bbox.xmax,
                        "ymax": obj.bbox.ymax,
                    },
                    "relative": False,
                }
            )
        item["result"] = processed_objects


class EdgeTPUClassification(EdgeTPU):
    """EdgeTPU image classification interface."""

    def work_input(self, item):
        """Perform image classification.

        Some models have unique input quantization values and require additional
        preprocessing.
        """
        params = common.input_details(self.interpreter, "quantization_parameters")
        scale = params["scales"]
        zero_point = params["zero_points"]
        mean = 128.0
        std = 128.0
        if abs(scale * std - 1) < 1e-5 and abs(mean - zero_point) < 1e-5:
            # Input data does not require preprocessing.
            common.set_input(self.interpreter, item["frame"])
        else:
            # Input data requires preprocessing
            normalized_input = (np.asarray(item["frame"]) - mean) / (
                std * scale
            ) + zero_point
            np.clip(normalized_input, 0, 255, out=normalized_input)
            common.set_input(self.interpreter, normalized_input.astype(np.uint8))

        self.interpreter.invoke()
        classifications = []
        for classification in classify.get_classes(self.interpreter, top_k=1):
            classifications.append(
                {
                    "label": classification.id,
                    "score": float(classification.score),
                }
            )
        item["result"] = classifications


def setup_logger(loglevel: str) -> None:
    """Log to stdout without any formatting.

    Viserons main log formatter takes care of the format in the main process.
    """
    root = logging.getLogger()
    root.setLevel(loglevel)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(loglevel)
    formatter = logging.Formatter("%(levelname)s %(message)s")
    handler.setFormatter(formatter)
    root.addHandler(handler)


def get_parser() -> argparse.ArgumentParser:
    """Get parser for script."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--manager-port", help="Port for the Manager", required=True)
    parser.add_argument(
        "--manager-authkey", help="Password for the Manager", required=True
    )
    parser.add_argument("--device", help="Device to run model on", required=True)
    parser.add_argument("--model", help="Path to model", required=True)
    parser.add_argument(
        "--model-type",
        help="Type of model",
        required=True,
        choices=["object_detector", "image_classification"],
    )
    parser.add_argument(
        "--loglevel",
        help="Loglevel",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    return parser


def main():
    """Run EdgeTPU in a Python 3.9 subprocess."""
    parser = get_parser()
    args = parser.parse_args()
    setup_logger(args.loglevel)
    process_queue, output_queue = connect(
        "127.0.0.1", int(args.manager_port), args.manager_authkey
    )

    edgetpu_type: type[EdgeTPUDetection] | type[EdgeTPUClassification]
    # Invoke correct class based on model type
    if args.model_type == "object_detector":
        edgetpu_type = EdgeTPUDetection
    else:
        edgetpu_type = EdgeTPUClassification

    try:
        edgetpu = edgetpu_type(
            device=args.device,
            model=args.model,
        )
    except MakeInterpreterError:
        LOGGER.error("Failed to make interpreter")
        output_queue.put("init_failed")
        sys.exit(1)

    LOGGER.debug("Sending init_done")
    output_queue.put("init_done")

    LOGGER.debug("Starting loop")
    while True:
        job = process_queue.get()
        if job == "get_model_size":
            model_width, model_height = edgetpu.get_model_size()
            output_queue.put(
                {
                    "get_model_size": {
                        "model_width": model_width,
                        "model_height": model_height,
                    }
                }
            )
            continue

        edgetpu.work_input(job)
        output_queue.put(job)


if __name__ == "__main__":
    main()
