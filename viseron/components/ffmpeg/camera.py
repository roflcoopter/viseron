"""FFmpeg camera."""
from __future__ import annotations

import multiprocessing as mp
import os
import time
from queue import Empty, Full
from typing import TYPE_CHECKING

import cv2
import setproctitle
import voluptuous as vol

from viseron import Viseron
from viseron.const import ENV_CUDA_SUPPORTED, ENV_VAAPI_SUPPORTED
from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.config import (
    BASE_CONFIG_SCHEMA as BASE_CAMERA_CONFIG_SCHEMA,
    DEFAULT_RECORDER,
    RECORDER_SCHEMA as BASE_RECORDER_SCHEMA,
)
from viseron.domains.camera.shared_frames import SharedFrame
from viseron.exceptions import DomainNotReady, FFprobeError, FFprobeTimeout
from viseron.helpers import escape_string, utcnow
from viseron.helpers.logs import SensitiveInformationFilter
from viseron.helpers.validators import (
    CameraIdentifier,
    CoerceNoneToDict,
    Deprecated,
    Maybe,
)
from viseron.watchdog.process_watchdog import RestartableProcess
from viseron.watchdog.thread_watchdog import RestartableThread

from .const import (
    COMPONENT,
    CONFIG_AUDIO_CODEC,
    CONFIG_CODEC,
    CONFIG_FFMPEG_LOGLEVEL,
    CONFIG_FFMPEG_RECOVERABLE_ERRORS,
    CONFIG_FFPROBE_LOGLEVEL,
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
    CONFIG_PROTOCOL,
    CONFIG_RAW_COMMAND,
    CONFIG_RECORD_ONLY,
    CONFIG_RECORDER,
    CONFIG_RECORDER_AUDIO_CODEC,
    CONFIG_RECORDER_AUDIO_FILTERS,
    CONFIG_RECORDER_CODEC,
    CONFIG_RECORDER_HWACCEL_ARGS,
    CONFIG_RECORDER_OUPTUT_ARGS,
    CONFIG_RECORDER_VIDEO_FILTERS,
    CONFIG_RTSP_TRANSPORT,
    CONFIG_SEGMENTS_FOLDER,
    CONFIG_STREAM_FORMAT,
    CONFIG_SUBSTREAM,
    CONFIG_USERNAME,
    CONFIG_VIDEO_FILTERS,
    CONFIG_WIDTH,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_CODEC,
    DEFAULT_FFMPEG_LOGLEVEL,
    DEFAULT_FFMPEG_RECOVERABLE_ERRORS,
    DEFAULT_FFPROBE_LOGLEVEL,
    DEFAULT_FPS,
    DEFAULT_FRAME_TIMEOUT,
    DEFAULT_GLOBAL_ARGS,
    DEFAULT_HEIGHT,
    DEFAULT_HWACCEL_ARGS,
    DEFAULT_INPUT_ARGS,
    DEFAULT_PASSWORD,
    DEFAULT_PIX_FMT,
    DEFAULT_PROTOCOL,
    DEFAULT_RAW_COMMAND,
    DEFAULT_RECORD_ONLY,
    DEFAULT_RECORDER_AUDIO_CODEC,
    DEFAULT_RECORDER_AUDIO_FILTERS,
    DEFAULT_RECORDER_CODEC,
    DEFAULT_RECORDER_HWACCEL_ARGS,
    DEFAULT_RECORDER_OUTPUT_ARGS,
    DEFAULT_RECORDER_VIDEO_FILTERS,
    DEFAULT_RTSP_TRANSPORT,
    DEFAULT_STREAM_FORMAT,
    DEFAULT_SUBSTREAM,
    DEFAULT_USERNAME,
    DEFAULT_VIDEO_FILTERS,
    DEFAULT_WIDTH,
    DESC_AUDIO_CODEC,
    DESC_CODEC,
    DESC_FFMPEG_LOGLEVEL,
    DESC_FFMPEG_RECOVERABLE_ERRORS,
    DESC_FFPROBE_LOGLEVEL,
    DESC_FPS,
    DESC_FRAME_TIMEOUT,
    DESC_GLOBAL_ARGS,
    DESC_HEIGHT,
    DESC_HOST,
    DESC_HWACCEL_ARGS,
    DESC_INPUT_ARGS,
    DESC_PASSWORD,
    DESC_PATH,
    DESC_PIX_FMT,
    DESC_PORT,
    DESC_PROTOCOL,
    DESC_RAW_COMMAND,
    DESC_RECORD_ONLY,
    DESC_RECORDER,
    DESC_RECORDER_AUDIO_CODEC,
    DESC_RECORDER_AUDIO_FILTERS,
    DESC_RECORDER_CODEC,
    DESC_RECORDER_FFMPEG_LOGLEVEL,
    DESC_RECORDER_HWACCEL_ARGS,
    DESC_RECORDER_OUTPUT_ARGS,
    DESC_RECORDER_VIDEO_FILTERS,
    DESC_RTSP_TRANSPORT,
    DESC_SEGMENTS_FOLDER,
    DESC_STREAM_FORMAT,
    DESC_SUBSTREAM,
    DESC_USERNAME,
    DESC_VIDEO_FILTERS,
    DESC_WIDTH,
    FFMPEG_LOGLEVELS,
    HWACCEL_VAAPI,
    STREAM_FORMAT_MAP,
)
from .recorder import Recorder
from .stream import Stream

if TYPE_CHECKING:
    from viseron.components.nvr.nvr import FrameIntervalCalculator
    from viseron.components.storage.models import TriggerTypes
    from viseron.domains.object_detector.detected_object import DetectedObject


def get_default_hwaccel_args() -> list[str]:
    """Return hardware acceleration args for FFmpeg."""
    # Dont enable VA-API if CUDA is available
    if (
        os.getenv(ENV_VAAPI_SUPPORTED) == "true"
        and os.getenv(ENV_CUDA_SUPPORTED) != "true"
    ):
        return HWACCEL_VAAPI
    return DEFAULT_HWACCEL_ARGS


STREAM_SCEHMA_DICT = {
    vol.Required(CONFIG_PATH, description=DESC_PATH): vol.All(str, vol.Length(min=1)),
    vol.Required(CONFIG_PORT, description=DESC_PORT): vol.All(int, vol.Range(min=1)),
    vol.Optional(
        CONFIG_STREAM_FORMAT,
        default=DEFAULT_STREAM_FORMAT,
        description=DESC_STREAM_FORMAT,
    ): vol.In(STREAM_FORMAT_MAP.keys()),
    vol.Optional(
        CONFIG_PROTOCOL, default=DEFAULT_PROTOCOL, description=DESC_PROTOCOL
    ): Maybe(vol.Any("rtsp", "rtsps", "rtmp", "http", "https")),
    vol.Optional(CONFIG_WIDTH, default=DEFAULT_WIDTH, description=DESC_WIDTH): Maybe(
        int
    ),
    vol.Optional(CONFIG_HEIGHT, default=DEFAULT_HEIGHT, description=DESC_HEIGHT): Maybe(
        int
    ),
    vol.Optional(CONFIG_FPS, default=DEFAULT_FPS, description=DESC_FPS): Maybe(
        vol.All(int, vol.Range(min=1))
    ),
    vol.Optional(
        CONFIG_INPUT_ARGS, default=DEFAULT_INPUT_ARGS, description=DESC_INPUT_ARGS
    ): Maybe(list),
    vol.Optional(
        CONFIG_HWACCEL_ARGS,
        default=get_default_hwaccel_args(),
        description=DESC_HWACCEL_ARGS,
    ): Maybe(list),
    vol.Optional(CONFIG_CODEC, default=DEFAULT_CODEC, description=DESC_CODEC): str,
    vol.Optional(
        CONFIG_AUDIO_CODEC, default=DEFAULT_AUDIO_CODEC, description=DESC_AUDIO_CODEC
    ): Maybe(str),
    vol.Optional(
        CONFIG_RTSP_TRANSPORT,
        default=DEFAULT_RTSP_TRANSPORT,
        description=DESC_RTSP_TRANSPORT,
    ): vol.Any("tcp", "udp", "udp_multicast", "http"),
    vol.Optional(
        CONFIG_VIDEO_FILTERS,
        default=DEFAULT_VIDEO_FILTERS,
        description=DESC_VIDEO_FILTERS,
    ): list,
    vol.Optional(
        CONFIG_PIX_FMT, default=DEFAULT_PIX_FMT, description=DESC_PIX_FMT
    ): vol.Any("nv12", "yuv420p"),
    vol.Optional(
        CONFIG_FRAME_TIMEOUT,
        default=DEFAULT_FRAME_TIMEOUT,
        description=DESC_FRAME_TIMEOUT,
    ): vol.All(int, vol.Range(1, 60)),
    vol.Optional(
        CONFIG_RAW_COMMAND,
        default=DEFAULT_RAW_COMMAND,
        description=DESC_RAW_COMMAND,
    ): Maybe(str),
}

FFMPEG_LOGLEVEL_SCEHMA = vol.Schema(vol.In(FFMPEG_LOGLEVELS.keys()))

RECORDER_SCHEMA = BASE_RECORDER_SCHEMA.extend(
    {
        vol.Optional(
            CONFIG_RECORDER_HWACCEL_ARGS,
            default=DEFAULT_RECORDER_HWACCEL_ARGS,
            description=DESC_RECORDER_HWACCEL_ARGS,
        ): [str],
        vol.Optional(
            CONFIG_RECORDER_CODEC,
            default=DEFAULT_RECORDER_CODEC,
            description=DESC_RECORDER_CODEC,
        ): str,
        vol.Optional(
            CONFIG_RECORDER_AUDIO_CODEC,
            default=DEFAULT_RECORDER_AUDIO_CODEC,
            description=DESC_RECORDER_AUDIO_CODEC,
        ): Maybe(str),
        vol.Optional(
            CONFIG_RECORDER_VIDEO_FILTERS,
            default=DEFAULT_RECORDER_VIDEO_FILTERS,
            description=DESC_RECORDER_VIDEO_FILTERS,
        ): [str],
        vol.Optional(
            CONFIG_RECORDER_AUDIO_FILTERS,
            default=DEFAULT_RECORDER_AUDIO_FILTERS,
            description=DESC_RECORDER_AUDIO_FILTERS,
        ): [str],
        vol.Optional(
            CONFIG_RECORDER_OUPTUT_ARGS,
            default=DEFAULT_RECORDER_OUTPUT_ARGS,
            description=DESC_RECORDER_OUTPUT_ARGS,
        ): [str],
        Deprecated(
            CONFIG_SEGMENTS_FOLDER,
            description=DESC_SEGMENTS_FOLDER,
        ): str,
        vol.Optional(
            CONFIG_FFMPEG_LOGLEVEL,
            default=DEFAULT_FFMPEG_LOGLEVEL,
            description=DESC_RECORDER_FFMPEG_LOGLEVEL,
        ): FFMPEG_LOGLEVEL_SCEHMA,
    }
)

CAMERA_SCHEMA = BASE_CAMERA_CONFIG_SCHEMA.extend(STREAM_SCEHMA_DICT)

CAMERA_SCHEMA = CAMERA_SCHEMA.extend(
    {
        vol.Required(CONFIG_HOST, description=DESC_HOST): str,
        vol.Optional(
            CONFIG_USERNAME, default=DEFAULT_USERNAME, description=DESC_USERNAME
        ): Maybe(str),
        vol.Optional(
            CONFIG_PASSWORD, default=DEFAULT_PASSWORD, description=DESC_PASSWORD
        ): Maybe(str),
        vol.Optional(
            CONFIG_GLOBAL_ARGS,
            default=DEFAULT_GLOBAL_ARGS,
            description=DESC_GLOBAL_ARGS,
        ): list,
        vol.Optional(
            CONFIG_SUBSTREAM, default=DEFAULT_SUBSTREAM, description=DESC_SUBSTREAM
        ): Maybe(vol.Schema(STREAM_SCEHMA_DICT)),
        vol.Optional(
            CONFIG_FFMPEG_LOGLEVEL,
            default=DEFAULT_FFMPEG_LOGLEVEL,
            description=DESC_FFMPEG_LOGLEVEL,
        ): FFMPEG_LOGLEVEL_SCEHMA,
        vol.Optional(
            CONFIG_FFMPEG_RECOVERABLE_ERRORS,
            default=DEFAULT_FFMPEG_RECOVERABLE_ERRORS,
            description=DESC_FFMPEG_RECOVERABLE_ERRORS,
        ): [str],
        vol.Optional(
            CONFIG_FFPROBE_LOGLEVEL,
            default=DEFAULT_FFPROBE_LOGLEVEL,
            description=DESC_FFPROBE_LOGLEVEL,
        ): FFMPEG_LOGLEVEL_SCEHMA,
        vol.Optional(
            CONFIG_RECORDER, default=DEFAULT_RECORDER, description=DESC_RECORDER
        ): vol.All(CoerceNoneToDict(), RECORDER_SCHEMA),
        vol.Optional(
            CONFIG_RECORD_ONLY,
            default=DEFAULT_RECORD_ONLY,
            description=DESC_RECORD_ONLY,
        ): bool,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        CameraIdentifier(): CAMERA_SCHEMA,
    }
)


def setup(vis: Viseron, config, identifier) -> bool:
    """Set up the ffmpeg camera domain."""
    try:
        Camera(vis, config[identifier], identifier)
    except (FFprobeError, FFprobeTimeout) as error:
        raise DomainNotReady from error
    return True


class Camera(AbstractCamera):
    """Represents a camera which is consumed via FFmpeg."""

    def __init__(self, vis: Viseron, config, identifier) -> None:
        # Add password to SensitiveInformationFilter.
        # It is done in AbstractCamera but since we are calling Stream before
        # super().__init__ we need to do it here as well
        if config[CONFIG_PASSWORD]:
            SensitiveInformationFilter.add_sensitive_string(config[CONFIG_PASSWORD])
            SensitiveInformationFilter.add_sensitive_string(
                escape_string(config[CONFIG_PASSWORD])
            )

        self._poll_timer = utcnow().timestamp()
        self._frame_reader = None
        self._frame_relay = None
        # Stream must be initialized before super().__init__ is called as it raises
        # FFprobeError/FFprobeTimeout which is caught in setup() and re-raised as
        # DomainNotReady
        self.stream = Stream(config, self, identifier)

        super().__init__(vis, COMPONENT, config, identifier)
        self._frame_queue: mp.Queue[  # pylint: disable=unsubscriptable-object
            bytes
        ] = mp.Queue(maxsize=2)
        self._capture_frames = mp.Event()
        self._thread_stuck = False
        self.resolution = None
        self.decode_error = mp.Event()

        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)
        vis.data[COMPONENT][self.identifier] = self
        self._recorder = Recorder(vis, config, self)

        self.initialize_camera()

    def _create_frame_reader(self):
        """Return a frame reader thread."""
        return RestartableProcess(
            name="viseron.camera." + self.identifier,
            args=(self._frame_queue,),
            target=self.read_frames,
            daemon=True,
            register=True,
        ), RestartableThread(
            name="viseron.camera." + self.identifier + ".relay_frame",
            target=self.relay_frame,
            poll_method=self.poll_method,
            poll_target=self.poll_target,
            daemon=True,
            register=True,
            restart_method=self.start_camera,
        )

    def _start_recording_only(self):
        """Record segments only.

        Used when output_frames is False which means we are only using the camera for
        storing recordings and not for image processing.
        """
        self._logger.debug("Starting recording only mode")

        def check_segment_process():
            while self.is_on:
                time.sleep(1)
                if (
                    self.stream.segment_process
                    and self.stream.segment_process.subprocess.poll() is None
                ):
                    self.connected = True
                    continue
                self.connected = False
            self.connected = False

        RestartableThread(
            name="viseron.camera." + self.identifier + ".segment_check",
            target=check_segment_process,
            daemon=True,
            register=True,
        ).start()

        self.stream.record_only()

    def initialize_camera(self) -> None:
        """Start processing of camera frames."""
        self._logger.debug(f"Initializing camera {self.name}")

        self.resolution = self.stream.width, self.stream.height
        self._logger.debug(
            f"Resolution: {self.resolution[0]}x{self.resolution[1]} "
            f"@ {self.stream.fps} FPS"
        )

        self._logger.debug(f"Camera {self.name} initialized")

    def read_frames(
        self,
        frame_queue: mp.Queue[bytes],  # pylint: disable=unsubscriptable-object
    ) -> None:
        """Read frames from camera."""
        setproctitle.setproctitle("viseron.camera." + self.identifier + ".read_frames")
        self.decode_error.clear()
        empty_frames = 0
        self._thread_stuck = False

        self.stream.start_pipe()

        while self._capture_frames.is_set():
            if self.decode_error.is_set():
                time.sleep(5)
                self._logger.error("Restarting frame pipe")
                self.stream.close_pipe()
                self.stream.start_pipe()
                self.decode_error.clear()
                empty_frames = 0

            frame_bytes = self.stream.read()
            if frame_bytes:
                empty_frames = 0
                # Dont queue frames if consumer is not ready
                try:
                    frame_queue.put_nowait(frame_bytes)
                except Full:
                    pass
                continue

            if self._thread_stuck:
                return

            if self.stream.poll() is not None:
                self._logger.error("Frame reader process has exited")
                self.decode_error.set()
                continue

            empty_frames += 1
            if empty_frames >= 10:
                self._logger.error("Did not receive a frame")
                self.decode_error.set()

        self.stream.close_pipe()
        self._logger.debug("Frame reader stopped")

    def relay_frame(self):
        """Read from the frame queue and create a SharedFrame."""
        self._poll_timer = utcnow().timestamp()
        while self._capture_frames.is_set():
            if self.decode_error.is_set():
                self.connected = False
                self.still_image_available = self.still_image_configured

            try:
                frame_bytes = self._frame_queue.get(timeout=1)
            except Empty:
                continue

            self.connected = True
            self.still_image_available = True

            if len(frame_bytes) == self.stream.frame_bytes_size:
                shared_frame = SharedFrame(
                    self.stream.color_plane_width,
                    self.stream.color_plane_height,
                    self.stream.pixel_format,
                    (self.stream.width, self.stream.height),
                    self.identifier,
                )
            else:
                continue

            self._poll_timer = utcnow().timestamp()
            self.shared_frames.create(shared_frame, frame_bytes)
            self.current_frame = shared_frame
            self._data_stream.publish_data(self.frame_bytes_topic, self.current_frame)

        self.connected = False
        self.still_image_available = self.still_image_configured

    def poll_target(self) -> None:
        """Close pipe when RestartableThread.poll_timeout has been reached."""
        self._logger.error("Timeout waiting for frame")
        self._thread_stuck = True
        self.stop_camera()

    def poll_method(self) -> bool:
        """Return true on frame timeout for RestartableThread to trigger a restart."""
        now = utcnow().timestamp()

        # Make sure we timeout at some point if we never get the first frame.
        if now - self._poll_timer > (DEFAULT_FRAME_TIMEOUT * 2):
            return True

        if not self.connected:
            return False

        if now - self._poll_timer > self._config[CONFIG_FRAME_TIMEOUT]:
            return True
        return False

    def calculate_output_fps(self, scanners: list[FrameIntervalCalculator]) -> None:
        """Calculate the camera output fps based on registered frame scanners.

        Overrides AbstractCamera.calculate_output_fps since we can't use the default
        implementation if the user has entered a raw pipeline.
        """
        if self._config[CONFIG_RAW_COMMAND]:
            self.output_fps = self.stream.fps
            return

        return super().calculate_output_fps(scanners)

    def _start_camera(self) -> None:
        """Start capturing frames from camera."""
        if self._config[CONFIG_RECORD_ONLY]:
            self._start_recording_only()
            return

        self._logger.debug("Starting capture thread")
        self._capture_frames.set()
        if not self._frame_reader or not self._frame_reader.is_alive():
            self._frame_reader, self._frame_relay = self._create_frame_reader()
            self._frame_reader.start()
            self._frame_relay.start()

    def _stop_camera(self) -> None:
        """Release the connection to the camera."""
        self._logger.debug("Stopping capture thread")
        self._capture_frames.clear()
        if self._frame_relay:
            self._frame_relay.stop()
            self._frame_relay.join(timeout=5)

        if self._frame_reader:
            self._frame_reader.join(timeout=5)
            self._frame_reader.terminate()
            if self._frame_reader.is_alive():
                self._logger.debug("Timed out trying to stop camera. Killing pipe")
                self._frame_reader.terminate()
                self._frame_reader.kill()
                self.stream.close_pipe()

    def start_recorder(
        self,
        shared_frame: SharedFrame,
        objects_in_fov: list[DetectedObject] | None,
        trigger_type: TriggerTypes,
    ) -> None:
        """Start camera recorder."""
        self._recorder.start(
            shared_frame, objects_in_fov if objects_in_fov else [], trigger_type
        )

    def stop_recorder(self) -> None:
        """Stop camera recorder."""
        self._recorder.stop(self.recorder.active_recording)

    @property
    def output_fps(self):
        """Set stream output fps."""
        return self.stream.output_fps

    @output_fps.setter
    def output_fps(self, fps) -> None:
        self.stream.output_fps = fps

    @property
    def resolution(self):
        """Return stream resolution."""
        return self._resolution

    @resolution.setter
    def resolution(self, resolution) -> None:
        """Return stream resolution."""
        self._resolution = resolution

    @property
    def mainstream_resolution(self) -> tuple[int, int]:
        """Return mainstream resolution."""
        return self.stream.mainstream.width, self.stream.mainstream.height

    @property
    def recorder(self) -> Recorder:
        """Return recorder instance."""
        return self._recorder

    @property
    def is_recording(self):
        """Return recording status."""
        return self._recorder.is_recording
