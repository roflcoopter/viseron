"""Run OpenCV Darknet in a separate shell since OpenCV does not cope with forking."""


import argparse
import logging
import sys

import cv2

from manager import connect

LOGGER = logging.getLogger(__name__)


class DarknetDNN:
    """Darknet DNN interface."""

    def __init__(
        self,
        model_width: int,
        model_height: int,
        model_path: str,
        model_config: str,
        backend: int,
        target: int,
    ):
        LOGGER.debug("Using OpenCV DNN Darknet")
        self.model_width = model_width
        self.model_height = model_height
        self.backend = backend
        self.target = target

        if cv2.ocl.haveOpenCL():
            LOGGER.debug("Enabling OpenCL")
            cv2.ocl.setUseOpenCL(True)

        LOGGER.debug(f"DNN backend: {self.backend}")
        LOGGER.debug(f"DNN target: {self.target}")

        self.load_network(
            model_path,
            model_config,
            self.backend,
            self.target,
        )

        LOGGER.debug("Darknet initialized")

    def load_network(
        self, model: str, model_config: str, backend: int, target: int
    ) -> None:
        """Load network."""
        self._net = cv2.dnn.readNet(model, model_config, "darknet")
        self._net.setPreferableBackend(backend)
        self._net.setPreferableTarget(target)

        self._model = cv2.dnn_DetectionModel(self._net)  # type: ignore[attr-defined]
        self._model.setInputParams(
            size=(self.model_width, self.model_height), scale=1 / 255
        )

    def work_input(self, item):
        """Perform object detection."""
        objs = self._model.detect(
            cv2.UMat(item["frame"]),
            item["min_confidence"],
            item["nms"],
        )
        item["result"] = objs


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

    parser.add_argument("--model-path", help="Path to model", required=True)
    parser.add_argument("--model-config", help="Path to model config", required=True)
    parser.add_argument("--model-width", help="Model width", required=True, type=int)
    parser.add_argument("--model-height", help="Model height", required=True, type=int)
    parser.add_argument("--backend", help="DNN backend", required=True, type=int)
    parser.add_argument("--target", help="DNN target", required=True, type=int)

    parser.add_argument(
        "--loglevel",
        help="Loglevel",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    return parser


def main():
    """Run Darknet in a subprocess."""
    parser = get_parser()
    args = parser.parse_args()
    setup_logger(args.loglevel)
    process_queue, output_queue = connect(
        "127.0.0.1", int(args.manager_port), args.manager_authkey
    )

    try:
        darknet = DarknetDNN(
            model_width=args.model_width,
            model_height=args.model_height,
            model_path=args.model_path,
            model_config=args.model_config,
            backend=args.backend,
            target=args.target,
        )
    except Exception:  # pylint: disable=broad-except
        LOGGER.error("Failed to initialize Darknet", exc_info=True)
        output_queue.put("init_failed")
        sys.exit(1)

    LOGGER.debug("Sending init_done")
    output_queue.put("init_done")

    LOGGER.debug("Starting loop")
    while True:
        job = process_queue.get()
        darknet.work_input(job)
        output_queue.put(job)


if __name__ == "__main__":
    main()
