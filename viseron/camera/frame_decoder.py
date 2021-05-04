"""Frame decoder."""
from __future__ import annotations

from dataclasses import dataclass
from queue import Queue
from threading import Event, Thread
from typing import Dict

from viseron.config import NVRConfig
from viseron.data_stream import DataStream
from viseron.exceptions import DuplicateDecoderName

from .frame import Frame
from .stream import Stream


@dataclass
class FrameToScan:
    """Class for a frame that is marked for scanning."""

    decoder_name: str
    frame: Frame
    stream_width: int
    stream_height: int
    camera_config: NVRConfig


class FrameDecoder:
    """Subscribes to raw frames and decodes them.
    Frames are then published to subsribers, object/motion detector.
    This makes it possible to decode frames in parallel with detection."""

    decoders: Dict[str, FrameDecoder] = {}

    def __init__(
        self,
        logger,
        config,
        name,
        interval,
        stream: Stream,
        decode_error,
        topic_decode,
        topic_scan,
        preprocess_callback=None,
    ):
        self._logger = logger
        self._config = config
        self.interval = interval
        self.interval_calculated = round(interval * stream.fps)
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

        decode_thread = Thread(target=self.decode_frame)
        decode_thread.daemon = True
        decode_thread.start()
        if self.decoders.get(name, None):
            raise DuplicateDecoderName(name)

        self._logger.debug(
            f"Running decoder {name} at {self.interval}s interval, "
            f"every {self.interval_calculated} frame(s)"
        )

        self.decoders[name] = self

    def scan_frame(self, current_frame):
        """Publish frame if marked for scanning."""
        if self.scan.is_set():
            if self._frame_number % self.interval_calculated == 0:
                self._frame_number = 0
                DataStream.publish_data(
                    self._topic_decode,
                    FrameToScan(
                        self,
                        current_frame,
                        self._stream.width,
                        self._stream.height,
                        self._config,
                    )
                    # {
                    #     "decoder_name": self,
                    #     "frame": current_frame,
                    #     "camera_config": self._config,
                    # },
                )

            self._frame_number += 1
        else:
            self._frame_number = 0

    def decode_frame(self):
        """Decodes received frames from scan_frame."""
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
