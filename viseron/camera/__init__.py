"""Camera communication."""
from __future__ import annotations

import datetime
import logging
from threading import Event
from time import sleep

import cv2

from viseron.const import TOPIC_FRAME_DECODE_OBJECT, TOPIC_FRAME_SCAN_OBJECT
from viseron.helpers.logs import SensitiveInformationFilter

from .frame_decoder import FrameDecoder
from .stream import Stream


class FFMPEGCamera:
    """Represents a camera which is consumed via FFmpeg."""

    def __init__(self, config, detector):
        self._logger = logging.getLogger(__name__ + "." + config.camera.name_slug)
        self._logger.addFilter(SensitiveInformationFilter())
        self._config = config
        self._connected = False
        self.resolution = None
        self._segments = None
        self.frame_ready = Event()
        self.decode_error = Event()

        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)

        self.initialize_camera(detector)

    def initialize_camera(self, detector):
        """Start processing of camera frames."""
        self._poll_timer = [None]
        self._logger = logging.getLogger(__name__ + "." + self._config.camera.name_slug)
        if getattr(self._config.camera.logging, "level", None):
            self._logger.setLevel(self._config.camera.logging.level)

        self._logger.debug("Initializing camera {}".format(self._config.camera.name))

        if self._config.camera.substream:
            self.stream = Stream(
                self._config,
                self._config.camera.substream,
                write_segments=False,
                pipe_frames=True,
            )
            self._segments = Stream(
                self._config,
                self._config.camera,
                write_segments=True,
                pipe_frames=False,
            )
        else:
            self.stream = Stream(
                self._config,
                self._config.camera,
                write_segments=True,
                pipe_frames=True,
            )

        self.resolution = self.stream.width, self.stream.height
        self._logger.debug(
            f"Resolution: {self.resolution[0]}x{self.resolution[1]} "
            f"@ {self.stream.fps} FPS"
        )

        FrameDecoder(
            self._logger,
            self._config,
            f"{self._config.camera.name_slug}.object_detection",
            self._config.object_detection.interval,
            self.stream,
            self.decode_error,
            TOPIC_FRAME_DECODE_OBJECT,
            TOPIC_FRAME_SCAN_OBJECT,
            preprocess_callback=detector.object_detector.preprocess,
        )

        self._logger.debug(f"Camera {self._config.camera.name} initialized")

    def capture_pipe(self):
        """Start capturing frames from camera."""
        self._logger.debug("Starting capture thread")
        self._connected = True
        self.decode_error.clear()
        self._poll_timer[0] = datetime.datetime.now().timestamp()
        empty_frames = 0

        self.stream.start_pipe()
        if self._segments:
            self._segments.start_pipe()

        while self._connected:
            if self.decode_error.is_set():
                sleep(5)
                self._logger.error("Restarting frame pipe")
                self.stream.close_pipe()
                self.stream.check_command()
                self.stream.start_pipe()
                self.decode_error.clear()
                empty_frames = 0

            current_frame = self.stream.read()
            if current_frame:
                empty_frames = 0
                self._poll_timer[0] = datetime.datetime.now().timestamp()
                for decoder in self.stream.decoders.values():
                    decoder.scan_frame(current_frame)

                self.frame_ready.set()
                self.frame_ready.clear()
                continue

            if self.stream.poll is not None:
                self._logger.error("FFmpeg process has exited")
                self.decode_error.set()
                continue

            empty_frames += 1
            if empty_frames >= 10:
                self._logger.error("Did not receive a frame")
                self.decode_error.set()

        self.stream.close_pipe()
        if self._segments:
            self._segments.close_pipe()
        self._logger.info("FFMPEG frame grabber stopped")

    @property
    def poll_timer(self):
        """Return poll timer."""
        return self._poll_timer

    def release(self):
        """Release the connection to the camera."""
        self._connected = False
