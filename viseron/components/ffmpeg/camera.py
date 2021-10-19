"""FFmpeg camera."""

import datetime
import time
from threading import Event

import cv2

from viseron.components.data_stream import COMPONENT as DATA_STREAM_COMPONENT
from viseron.domains.camera import AbstractCamera

from .const import COMPONENT, RECORDER
from .recorder import Recorder
from .stream import Stream


class Camera(AbstractCamera):
    """Represents a camera which is consumed via FFmpeg."""

    def __init__(self, vis, config):
        super().__init__(vis, config)
        self._connected = False
        self.resolution = None
        self.frame_ready = Event()
        self.decode_error = Event()

        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)

        self._recorder = Recorder(config, self.name)
        vis.data[COMPONENT][self.name] = {}
        vis.data[COMPONENT][self.name][RECORDER] = self._recorder

        self.initialize_camera()

    def initialize_camera(self):
        """Start processing of camera frames."""
        self._poll_timer = [None]
        self._logger.debug("Initializing camera {}".format(self.name))

        self.stream = Stream(self._vis, self._config, self.name)

        self.resolution = self.stream.width, self.stream.height
        self._logger.debug(
            f"Resolution: {self.resolution[0]}x{self.resolution[1]} "
            f"@ {self.stream.fps} FPS"
        )

        self._logger.debug(f"Camera {self.name} initialized")

    def start_camera(self):
        """Start capturing frames from camera."""
        self._logger.debug("Starting capture thread")
        self._connected = True
        self.decode_error.clear()
        self._poll_timer[0] = datetime.datetime.now().timestamp()
        empty_frames = 0

        self.stream.start_pipe()

        while self._connected:
            if self.decode_error.is_set():
                self._vis.data[DATA_STREAM_COMPONENT].publish_data(
                    f"{self.identifier}/status", "disconnected"
                )
                time.sleep(5)
                self._logger.error("Restarting frame pipe")
                self.stream.close_pipe()
                self.stream.start_pipe()
                self.decode_error.clear()
                empty_frames = 0

            current_frame = self.stream.read()
            if current_frame:
                empty_frames = 0
                self._poll_timer[0] = datetime.datetime.now().timestamp()

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
        self._logger.info("FFMPEG frame grabber stopped")

    @property
    def poll_timer(self):
        """Return poll timer."""
        return self._poll_timer

    def stop_camera(self):
        """Release the connection to the camera."""
        self._connected = False

    @property
    def resolution(self):
        """Return stream resolution."""
        return self._resolution

    @resolution.setter
    def resolution(self, resolution):
        """Return stream resolution."""
        self._resolution = resolution

    def start_recording(self):
        """Start camera recording."""
        return NotImplementedError()

    def stop_recording(self):
        """Stop camera recording."""
        return NotImplementedError()
