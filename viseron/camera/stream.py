"""Class to interact with an FFmpeog stream."""
from __future__ import annotations

import json
import logging
import os
import subprocess as sp
from typing import TYPE_CHECKING, Dict, Optional, Union

import cv2
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from viseron.camera.frame_decoder import FrameDecoder
from viseron.const import (
    CAMERA_SEGMENT_ARGS,
    ENV_FFMPEG_PATH,
    FFMPEG_LOG_LEVELS,
    FFPROBE_TIMEOUT,
)
from viseron.detector import Detector
from viseron.exceptions import FFprobeError, FFprobeTimeout, StreamInformationError
from viseron.helpers.logs import FFmpegFilter, LogPipe, SensitiveInformationFilter
from viseron.watchdog.subprocess_watchdog import RestartablePopen

from .frame import Frame

if TYPE_CHECKING:
    from viseron.config.config_camera import CameraConfig, Substream


class Stream:
    """Represents a stream of frames from a camera."""

    def __init__(
        self,
        config,
        stream_config: Union[CameraConfig, Substream],
        write_segments=True,
        pipe_frames=True,
    ):
        if write_segments and not pipe_frames:
            self._logger = logging.getLogger(
                __name__ + "_segments." + config.camera.name_slug
            )
        else:
            self._logger = logging.getLogger(__name__ + "." + config.camera.name_slug)
        self._logger.addFilter(SensitiveInformationFilter())
        self._logger.addFilter(FFmpegFilter(config.camera.ffmpeg_recoverable_errors))
        self._config = config
        self.stream_config = stream_config
        self._write_segments = write_segments
        self._pipe_frames = pipe_frames

        self._pipe = None
        self._log_pipe = LogPipe(
            self._logger, FFMPEG_LOG_LEVELS[config.camera.ffmpeg_loglevel]
        )

        self._ffprobe_log_pipe = LogPipe(
            self._logger, FFMPEG_LOG_LEVELS[config.camera.ffprobe_loglevel]
        )
        self._ffprobe_timeout = FFPROBE_TIMEOUT

        stream_codec = None
        stream_audio_codec = None
        # If any of the parameters are unset we need to fetch them using FFprobe
        if (
            not self.stream_config.width
            or not self.stream_config.height
            or not self.stream_config.fps
            or not self.stream_config.codec
            or self.stream_config.audio_codec == "unset"
        ):
            (
                width,
                height,
                fps,
                stream_codec,
                stream_audio_codec,
            ) = self.get_stream_information(self.stream_config.stream_url)

        self.width = self.stream_config.width if self.stream_config.width else width
        self.height = self.stream_config.height if self.stream_config.height else height
        self.fps = self.stream_config.fps if self.stream_config.fps else fps
        self._output_fps = self.fps
        self.stream_codec = stream_codec
        self.stream_audio_codec = stream_audio_codec

        if self.width and self.height and self.fps:
            pass
        else:
            raise StreamInformationError(self.width, self.height, self.fps)

        self.decoders: Dict[str, FrameDecoder] = {}
        self.create_symlink()

        if stream_config.pix_fmt == "nv12":
            self._color_converter = cv2.COLOR_YUV2RGB_NV21
            self._color_plane_width = self.width
            self._color_plane_height = int(self.height * 1.5)
            self._frame_bytes = int(self.width * self.height * 1.5)
        elif stream_config.pix_fmt == "yuv420p":
            self._color_converter = cv2.COLOR_YUV2BGR_I420
            self._color_plane_width = self.width
            self._color_plane_height = int(self.height * 1.5)
            self._frame_bytes = int(self.width * self.height * 1.5)

    @property
    def alias(self):
        """Return FFmpeg executable alias."""
        alias = self._config.camera.name_slug
        if self._write_segments and not self._pipe_frames:
            alias = f"{alias}_segments"
        return alias

    def create_symlink(self):
        """Create a symlink to FFmpeg executable.

        This is done to know which FFmpeg command belongs to which camera.
        """
        try:
            os.symlink(os.getenv(ENV_FFMPEG_PATH), f"/home/abc/bin/{self.alias}")
        except FileExistsError:
            pass

    @property
    def output_fps(self):
        """Return stream output FPS."""
        return self._output_fps

    @output_fps.setter
    def output_fps(self, value: bool):
        self._output_fps = value

    def calculate_output_fps(self):
        """Calculate FFmpeg output FPS."""
        max_interval_fps = 1 / min(
            [decoder.interval for decoder in self.decoders.values()]
        )
        self.output_fps = round(min([max_interval_fps, self.fps]))

    def run_ffprobe(
        self,
        stream_url: str,
    ) -> dict:
        """Run FFprobe command."""
        ffprobe_command = (
            [
                "ffprobe",
                "-hide_banner",
                "-loglevel",
            ]
            + [self._config.camera.ffprobe_loglevel]
            + [
                "-print_format",
                "json",
                "-show_error",
                "-show_streams",
            ]
            + [stream_url]
        )

        for attempt in Retrying(
            retry=retry_if_exception_type((sp.TimeoutExpired, FFprobeTimeout)),
            stop=stop_after_attempt(10),
            wait=wait_exponential(multiplier=2, min=1, max=30),
            before_sleep=before_sleep_log(self._logger, logging.ERROR),
            reraise=True,
        ):
            with attempt:
                with Detector.lock:
                    pipe = sp.Popen(  # type: ignore
                        ffprobe_command,
                        stdout=sp.PIPE,
                        stderr=self._log_pipe,
                    )
                try:
                    stdout, _ = pipe.communicate(timeout=self._ffprobe_timeout)
                    pipe.wait(timeout=FFPROBE_TIMEOUT)
                except sp.TimeoutExpired as error:
                    pipe.terminate()
                    pipe.wait(timeout=FFPROBE_TIMEOUT)
                    ffprobe_timeout = self._ffprobe_timeout
                    self._ffprobe_timeout += FFPROBE_TIMEOUT
                    raise FFprobeTimeout(ffprobe_command, ffprobe_timeout) from error
                else:
                    self._ffprobe_timeout = FFPROBE_TIMEOUT

        try:
            # Trim away any text before start of JSON object
            trimmed_stdout = stdout[stdout.find(b"{") :]
            output: dict = json.loads(trimmed_stdout)
        except json.decoder.JSONDecodeError as error:
            raise FFprobeError(
                stdout,
                ffprobe_command,
            ) from error

        if output.get("error", None):
            raise FFprobeError(
                output,
                ffprobe_command,
            )

        return output

    def ffprobe_stream_information(self, stream_url):
        """Return stream information using FFprobe."""
        width, height, fps, codec, audio_codec = 0, 0, 0, None, None
        streams = self.run_ffprobe(stream_url)

        video_stream = None
        audio_stream = None
        for stream in streams["streams"]:
            if video_stream and audio_stream:
                break
            if stream["codec_type"] == "video":
                video_stream = stream
            elif stream["codec_type"] == "audio":
                audio_stream = stream

        if audio_stream:
            audio_codec = audio_stream.get("codec_name", None)

        try:
            numerator = int(video_stream.get("avg_frame_rate", 0).split("/")[0])
            denominator = int(video_stream.get("avg_frame_rate", 0).split("/")[1])
        except KeyError:
            return (width, height, fps, codec, audio_codec)

        try:
            fps = numerator / denominator
        except ZeroDivisionError:
            pass

        width = video_stream.get("width", 0)
        height = video_stream.get("height", 0)
        codec = video_stream.get("codec_name", None)

        return (width, height, fps, codec, audio_codec)

    def get_stream_information(self, stream_url):
        """Return stream information."""
        self._logger.debug("Getting stream information for {}".format(stream_url))
        width, height, fps, codec, audio_codec = self.ffprobe_stream_information(
            stream_url
        )

        self._logger.debug(
            "Stream information from FFprobe: "
            f"Width: {width} "
            f"Height: {height} "
            f"FPS: {fps} "
            f"Video Codec: {codec} "
            f"Audio Codec: {audio_codec}"
        )
        return width, height, fps, codec, audio_codec

    @staticmethod
    def get_codec(stream_config, stream_codec):
        """Return codec set in config or from predefined codec map."""
        if stream_config.codec:
            return stream_config.codec

        if stream_codec:
            codec = stream_config.codec_map.get(stream_codec, None)
            if codec:
                return ["-c:v", codec]

        return []

    def stream_command(self, stream_config, stream_codec):
        """Return FFmpeg input stream."""
        return (
            stream_config.input_args
            + stream_config.hwaccel_args
            + self.get_codec(stream_config, stream_codec)
            + (
                ["-rtsp_transport", stream_config.rtsp_transport]
                if stream_config.stream_format == "rtsp"
                else []
            )
            + ["-i", stream_config.stream_url]
        )

    @staticmethod
    def get_audio_codec(
        stream_config: Union[CameraConfig, Substream], stream_audio_codec
    ):
        """Return audio codec used for saving segments."""
        if stream_config.audio_codec and stream_config.audio_codec != "unset":
            return ["-c:a", stream_config.audio_codec]

        if stream_audio_codec and stream_config.audio_codec == "unset":
            return ["-c:a", "copy"]

        return []

    def build_command(self, ffmpeg_loglevel=None, single_frame=False):
        """Return full FFmpeg command."""
        camera_segment_args = []
        if not single_frame and self._write_segments:
            segment_path = os.path.join(
                self._config.recorder.segments_folder,
                self._config.camera.name,
                f"%Y%m%d%H%M%S.{self._config.recorder.extension}",
            )
            camera_segment_args = (
                CAMERA_SEGMENT_ARGS
                + self.get_audio_codec(self.stream_config, self.stream_audio_codec)
                + [segment_path]
            )

        return (
            [self.alias]
            + self._config.camera.global_args
            + ["-loglevel"]
            + (
                [ffmpeg_loglevel]
                if ffmpeg_loglevel
                else [self._config.camera.ffmpeg_loglevel]
            )
            + self.stream_command(self.stream_config, self.stream_codec)
            + (["-frames:v", "1"] if single_frame else [])
            + camera_segment_args
            + (self._config.camera.filter_args if self._pipe_frames else [])
            + (
                ["-filter:v", f"fps={self.output_fps}"]
                if self.output_fps < self.fps
                else []
            )
            + (self._config.camera.output_args if self._pipe_frames else [])
        )

    def pipe(self, single_frame=False):
        """Return subprocess pipe for FFmpeg."""
        if single_frame:
            with Detector.lock:
                return sp.Popen(
                    self.build_command(
                        ffmpeg_loglevel="fatal", single_frame=single_frame
                    ),
                    stdout=sp.PIPE,
                    stderr=sp.PIPE,
                )

        if self._write_segments and not self._pipe_frames:
            return RestartablePopen(
                self.build_command(),
                stdout=sp.PIPE,
                stderr=self._log_pipe,
                name=self.alias,
            )

        with Detector.lock:
            return sp.Popen(
                self.build_command(),
                stdout=sp.PIPE,
                stderr=self._log_pipe,
            )

    def start_pipe(self):
        """Start piping frames from FFmpeg."""
        self._logger.debug(f"FFMPEG decoder command: {' '.join(self.build_command())}")
        self._pipe = self.pipe()

    def close_pipe(self):
        """Close FFmpeg pipe."""
        self._pipe.terminate()
        try:
            self._pipe.communicate(timeout=5)
        except sp.TimeoutExpired:
            self._logger.debug("FFmpeg did not terminate, killing instead.")
            self._pipe.kill()
            self._pipe.communicate()

    def poll(self):
        """Poll pipe."""
        return self._pipe.poll()

    def read(self) -> Optional[Frame]:
        """Return a single frame from FFmpeg pipe."""
        if self._pipe:
            frame_bytes = self._pipe.stdout.read(self._frame_bytes)

            if len(frame_bytes) == self._frame_bytes:
                return Frame(
                    self._color_converter,
                    self._color_plane_width,
                    self._color_plane_height,
                    frame_bytes,
                    self.width,
                    self.height,
                )
        return None
