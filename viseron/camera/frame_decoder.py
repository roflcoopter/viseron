"""Frame decoder."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from queue import Queue
from threading import Event
from typing import TYPE_CHECKING, Callable

from viseron.camera.frame import Frame
from viseron.data_stream import DataStream
from viseron.exceptions import DuplicateDecoderName
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from viseron.camera.stream import Stream
    from viseron.config import NVRConfig


@dataclass
class FrameToScan:
    """Class for a frame that is marked for scanning."""

    decoder_name: str
    frame: Frame
    stream_width: int
    stream_height: int
    camera_config: NVRConfig
    capture_time: float


class FrameDecoder:
    """Subscribes to raw frames and decodes them.

    Frames are then published to subsribers, object/motion detector.
    This makes it possible to decode frames in parallel with detection.
    """

    def __init__(
        self,
        logger: logging.Logger,
        config: NVRConfig,
        name: str,
        fps: float,
        stream: Stream,
        decode_error: Event,
        topic_decode: str,
        topic_scan: str,
        preprocess_callback: Callable = None,
    ):
        self._logger = logger
        self._config = config
        self.name = name
        self.fps = fps
        self._frame_interval = None
        self._stream = stream
        self.decode_error = False
        self.scan = Event()
        self._frame_number = 0
        self._decode_error = decode_error
        self._decoder_queue: Queue = Queue(maxsize=5)
        self._preprocessor_callback = preprocess_callback

        self._topic_scan = f"{config.camera.name_slug}/{topic_scan}"
        self._topic_decode = f"{config.camera.name_slug}/{topic_decode}"
        DataStream.subscribe_data(self._topic_decode, self._decoder_queue)

        decode_thread = RestartableThread(
            name=__name__ + "." + config.camera.name_slug,
            target=self.decode_frame,
            daemon=True,
            register=True,
        )
        decode_thread.start()

        if stream.decoders.get(name, None):
            raise DuplicateDecoderName(name)
        stream.decoders[name] = self
        stream.calculate_output_fps()

        if self.fps > self._stream.output_fps:
            self._logger.warning(
                f"FPS for decoder {name} is too high, "
                f"highest possible FPS is {self._stream.output_fps}"
            )
            self.fps = self._stream.output_fps

        for decoder in stream.decoders.values():
            decoder.calculate_interval()  # Re-calculate interval for all decoders

        self._logger.debug(f"Running decoder {name} at {self.fps} FPS")

    def calculate_interval(self):
        """Calculate which frames are to be processed."""
        self._frame_interval = round(self._stream.output_fps / self.fps)

    def scan_frame(self, current_frame):
        """Publish frame if marked for scanning."""
        if self.scan.is_set():
            if self._frame_number % self._frame_interval == 0:
                self._frame_number = 0
                DataStream.publish_data(
                    self._topic_decode,
                    FrameToScan(
                        self.name,
                        current_frame,
                        self._stream.width,
                        self._stream.height,
                        self._config,
                        time.time(),
                    ),
                )

            self._frame_number += 1
        else:
            self._frame_number = 0

    def decode_frame(self):
        """Decode received frame from scan_frame."""
        self._logger.debug("Starting decoder thread")
        while True:
            frame_to_scan: FrameToScan = self._decoder_queue.get()
            if frame_to_scan.frame.decode_frame():
                if self._preprocessor_callback:
                    self._preprocessor_callback(frame_to_scan)
                DataStream.publish_data(self._topic_scan, frame_to_scan)
                continue

            self._decode_error.set()
            self._logger.error("Unable to decode frame. FFmpeg pipe seems broken")
