"""FFmpeg camera."""

import datetime
import os
import time
from threading import Event
from typing import List

import cv2
import voluptuous as vol

from viseron import Viseron
from viseron.const import ENV_CUDA_SUPPORTED, ENV_VAAPI_SUPPORTED
from viseron.domains.camera import (
    BASE_CONFIG_SCHEMA as BASE_CAMERA_CONFIG_SCHEMA,
    DEFAULT_RECORDER,
    EVENT_STATUS,
    EVENT_STATUS_CONNECTED,
    EVENT_STATUS_DISCONNECTED,
    RECORDER_SCHEMA as BASE_RECORDER_SCHEMA,
    AbstractCamera,
    EventStatusData,
)
from viseron.watchdog.thread_watchdog import RestartableThread

from .binary_sensor import ConnectionStatusBinarySensor
from .const import (
    COMPONENT,
    CONFIG_AUDIO_CODEC,
    CONFIG_CODEC,
    CONFIG_FFMPEG_LOGLEVEL,
    CONFIG_FFMPEG_RECOVERABLE_ERRORS,
    CONFIG_FFPROBE_LOGLEVEL,
    CONFIG_FILTER_ARGS,
    CONFIG_FPS,
    CONFIG_FRAME_TIMEOUT,
    CONFIG_GLOBAL_ARGS,
    CONFIG_HEIGHT,
    CONFIG_HOST,
    CONFIG_HWACCEL_ARGS,
    CONFIG_INPUT_ARGS,
    CONFIG_PASSWORD,
    CONFIG_PATH,
    CONFIG_PIX_FMT,
    CONFIG_PORT,
    CONFIG_RECORDER,
    CONFIG_RECORDER_AUDIO_CODEC,
    CONFIG_RECORDER_CODEC,
    CONFIG_RECORDER_FILTER_ARGS,
    CONFIG_RECORDER_HWACCEL_ARGS,
    CONFIG_RTSP_TRANSPORT,
    CONFIG_SEGMENTS_FOLDER,
    CONFIG_STREAM_FORMAT,
    CONFIG_SUBSTREAM,
    CONFIG_USERNAME,
    CONFIG_WIDTH,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_CODEC,
    DEFAULT_FFMPEG_LOGLEVEL,
    DEFAULT_FFMPEG_RECOVERABLE_ERRORS,
    DEFAULT_FFPROBE_LOGLEVEL,
    DEFAULT_FILTER_ARGS,
    DEFAULT_FPS,
    DEFAULT_FRAME_TIMEOUT,
    DEFAULT_GLOBAL_ARGS,
    DEFAULT_HEIGHT,
    DEFAULT_HWACCEL_ARGS,
    DEFAULT_INPUT_ARGS,
    DEFAULT_PASSWORD,
    DEFAULT_PIX_FMT,
    DEFAULT_RECORDER_AUDIO_CODEC,
    DEFAULT_RECORDER_CODEC,
    DEFAULT_RECORDER_FILTER_ARGS,
    DEFAULT_RECORDER_HWACCEL_ARGS,
    DEFAULT_RTSP_TRANSPORT,
    DEFAULT_SEGMENTS_FOLDER,
    DEFAULT_STREAM_FORMAT,
    DEFAULT_USERNAME,
    DEFAULT_WIDTH,
    FFMPEG_LOG_LEVELS,
    HWACCEL_VAAPI,
    STREAM_FORMAT_MAP,
)
from .recorder import Recorder
from .stream import Stream


def check_for_hwaccels(hwaccel_args: List[str]) -> List[str]:
    """Return hardware acceleration args for FFmpeg."""
    if hwaccel_args:
        return hwaccel_args

    # Dont enable VA-API if CUDA is available
    if (
        os.getenv(ENV_VAAPI_SUPPORTED) == "true"
        and os.getenv(ENV_CUDA_SUPPORTED) != "true"
    ):
        return HWACCEL_VAAPI
    return hwaccel_args


STREAM_SCEHMA_DICT = {
    vol.Optional(CONFIG_STREAM_FORMAT, default=DEFAULT_STREAM_FORMAT): vol.In(
        STREAM_FORMAT_MAP.keys()
    ),
    vol.Required(CONFIG_PATH): vol.All(str, vol.Length(min=1)),
    vol.Required(CONFIG_PORT): vol.All(int, vol.Range(min=1)),
    vol.Optional(CONFIG_WIDTH, default=DEFAULT_WIDTH): vol.Maybe(int),
    vol.Optional(CONFIG_HEIGHT, default=DEFAULT_HEIGHT): vol.Maybe(int),
    vol.Optional(CONFIG_FPS, default=DEFAULT_FPS): vol.Maybe(
        vol.All(int, vol.Range(min=1))
    ),
    vol.Optional(CONFIG_INPUT_ARGS, default=DEFAULT_INPUT_ARGS): vol.Maybe(list),
    vol.Optional(CONFIG_HWACCEL_ARGS, default=DEFAULT_HWACCEL_ARGS): check_for_hwaccels,
    vol.Optional(CONFIG_CODEC, default=DEFAULT_CODEC): str,
    vol.Optional(CONFIG_AUDIO_CODEC, default=DEFAULT_AUDIO_CODEC): vol.Maybe(str),
    vol.Optional(CONFIG_RTSP_TRANSPORT, default=DEFAULT_RTSP_TRANSPORT): vol.Any(
        "tcp", "udp", "udp_multicast", "http"
    ),
    vol.Optional(CONFIG_FILTER_ARGS, default=DEFAULT_FILTER_ARGS): list,
    vol.Optional(CONFIG_PIX_FMT, default=DEFAULT_PIX_FMT): vol.Any("nv12", "yuv420p"),
    vol.Optional(CONFIG_FRAME_TIMEOUT, default=DEFAULT_FRAME_TIMEOUT): int,
}

RECORDER_SCHEMA = BASE_RECORDER_SCHEMA.extend(
    {
        vol.Optional(
            CONFIG_RECORDER_HWACCEL_ARGS, default=DEFAULT_RECORDER_HWACCEL_ARGS
        ): [str],
        vol.Optional(CONFIG_RECORDER_CODEC, default=DEFAULT_RECORDER_CODEC): str,
        vol.Optional(
            CONFIG_RECORDER_AUDIO_CODEC, default=DEFAULT_RECORDER_AUDIO_CODEC
        ): str,
        vol.Optional(
            CONFIG_RECORDER_FILTER_ARGS, default=DEFAULT_RECORDER_FILTER_ARGS
        ): [str],
        vol.Optional(CONFIG_SEGMENTS_FOLDER, default=DEFAULT_SEGMENTS_FOLDER): str,
    }
)

FFMPEG_LOGLEVEL_SCEHMA = vol.Schema(vol.In(FFMPEG_LOG_LEVELS.keys()))

CAMERA_SCHEMA = BASE_CAMERA_CONFIG_SCHEMA.extend(STREAM_SCEHMA_DICT)

CAMERA_SCHEMA = CAMERA_SCHEMA.extend(
    {
        vol.Required(CONFIG_HOST): vol.All(str, vol.Length(min=1)),
        vol.Optional(CONFIG_USERNAME, default=DEFAULT_USERNAME): vol.Maybe(
            vol.All(str, vol.Length(min=1))
        ),
        vol.Optional(CONFIG_PASSWORD, default=DEFAULT_PASSWORD): vol.Maybe(
            vol.All(str, vol.Length(min=1))
        ),
        vol.Optional(CONFIG_GLOBAL_ARGS, default=DEFAULT_GLOBAL_ARGS): list,
        vol.Optional(CONFIG_SUBSTREAM): vol.Schema(STREAM_SCEHMA_DICT),
        vol.Optional(
            CONFIG_FFMPEG_LOGLEVEL, default=DEFAULT_FFMPEG_LOGLEVEL
        ): FFMPEG_LOGLEVEL_SCEHMA,
        vol.Optional(
            CONFIG_FFMPEG_RECOVERABLE_ERRORS, default=DEFAULT_FFMPEG_RECOVERABLE_ERRORS
        ): [str],
        vol.Optional(
            CONFIG_FFPROBE_LOGLEVEL, default=DEFAULT_FFPROBE_LOGLEVEL
        ): FFMPEG_LOGLEVEL_SCEHMA,
        vol.Optional(CONFIG_RECORDER, default=DEFAULT_RECORDER): RECORDER_SCHEMA,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        str: CAMERA_SCHEMA,
    }
)


def setup(vis: Viseron, config):
    """Set up the ffmpeg camera domain."""
    camera_identifier = list(config)[0]
    camera = Camera(vis, config[camera_identifier], camera_identifier)

    sensor = ConnectionStatusBinarySensor(vis, camera, "test_sensor")
    vis.add_entity(COMPONENT, sensor)


class Camera(AbstractCamera):
    """Represents a camera which is consumed via FFmpeg."""

    def __init__(self, vis, config, identifier):
        super().__init__(vis, config, identifier)
        self._frame_reader = None
        self._capture_frames = False
        self._connected = False
        self.resolution = None
        self.decode_error = Event()

        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)
        vis.data[COMPONENT][self.identifier] = self
        self._recorder = Recorder(vis, config, self)

        self.initialize_camera()
        vis.register_camera(self.identifier, self)

    def initialize_camera(self):
        """Start processing of camera frames."""
        self._poll_timer = [None]
        self._logger.debug("Initializing camera {}".format(self.name))

        self.stream = Stream(self._vis, self._config, self.identifier)

        self.resolution = self.stream.width, self.stream.height
        self._logger.debug(
            f"Resolution: {self.resolution[0]}x{self.resolution[1]} "
            f"@ {self.stream.fps} FPS"
        )

        self._logger.debug(f"Camera {self.name} initialized")

    def read_frames(self):
        """Read frames from camera."""
        self._capture_frames = True
        self.decode_error.clear()
        self._poll_timer[0] = datetime.datetime.now().timestamp()
        empty_frames = 0

        self.stream.start_pipe()

        while self._capture_frames:
            if self.decode_error.is_set():
                self.connected = False
                time.sleep(5)
                self._logger.error("Restarting frame pipe")
                self.stream.close_pipe()
                self.stream.start_pipe()
                self.decode_error.clear()
                empty_frames = 0

            current_frame = self.stream.read()
            if current_frame:
                self.connected = True
                empty_frames = 0
                self._poll_timer[0] = datetime.datetime.now().timestamp()
                self._data_stream.publish_data(self.frame_bytes_topic, current_frame)
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
        self._logger.debug("FFmpeg frame reader stopped")

    def start_camera(self):
        """Start capturing frames from camera."""
        self._logger.debug("Starting capture thread")
        if not self._frame_reader or not self._frame_reader.is_alive():
            self._frame_reader = RestartableThread(
                name="viseron.camera." + self.identifier,
                target=self.read_frames,
                poll_timer=self.poll_timer,
                poll_timeout=self._config[CONFIG_FRAME_TIMEOUT],
                poll_target=self.stop_camera,
                daemon=True,
                register=True,
            )
            self._frame_reader.start()

    def stop_camera(self):
        """Release the connection to the camera."""
        self._capture_frames = False
        self._frame_reader.join()

    def start_recorder(self, shared_frame, objects_in_fov):
        """Start camera recorder."""
        self._recorder.start(shared_frame, objects_in_fov, self.resolution)

    def stop_recorder(self):
        """Stop camera recorder."""
        self._recorder.stop()

    @property
    def connected(self):
        """Return if ffmpeg is connected to camera."""
        return self._connected

    @connected.setter
    def connected(self, connected):
        if connected == self._connected:
            return

        self._connected = connected
        self._vis.dispatch_event(
            EVENT_STATUS.format(camera_identifier=self.identifier),
            EventStatusData(
                status=EVENT_STATUS_CONNECTED
                if connected
                else EVENT_STATUS_DISCONNECTED
            ),
        )

    @property
    def poll_timer(self):
        """Return poll timer."""
        return self._poll_timer

    @property
    def output_fps(self):
        """Set stream output fps."""
        return self.stream.output_fps

    @output_fps.setter
    def output_fps(self, fps):
        self.stream.output_fps = fps

    @property
    def resolution(self):
        """Return stream resolution."""
        return self._resolution

    @resolution.setter
    def resolution(self, resolution):
        """Return stream resolution."""
        self._resolution = resolution

    @property
    def recorder(self) -> Recorder:
        """Return recorder instance."""
        return self._recorder

    @property
    def is_recording(self):
        """Return recording status."""
        return self._recorder.is_recording
