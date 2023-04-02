"""Class to interact with an FFmpeog stream."""
from __future__ import annotations

import json
import logging
import os
import subprocess as sp
from typing import TYPE_CHECKING

from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from viseron.components.ffmpeg.const import FFPROBE_LOGLEVELS, FFPROBE_TIMEOUT
from viseron.const import (
    ENV_CUDA_SUPPORTED,
    ENV_JETSON_NANO,
    ENV_RASPBERRYPI3,
    ENV_RASPBERRYPI4,
)
from viseron.domains.camera.shared_frames import SharedFrame
from viseron.exceptions import FFprobeError, FFprobeTimeout, StreamInformationError
from viseron.helpers.logs import LogPipe, UnhelpfullLogFilter

from .const import (
    CONFIG_AUDIO_CODEC,
    CONFIG_AUDIO_PIPELINE,
    CONFIG_CODEC,
    CONFIG_FFPROBE_LOGLEVEL,
    CONFIG_FPS,
    CONFIG_GSTREAMER_LOGLEVEL,
    CONFIG_GSTREAMER_RECOVERABLE_ERRORS,
    CONFIG_HEIGHT,
    CONFIG_HOST,
    CONFIG_PASSWORD,
    CONFIG_PATH,
    CONFIG_PORT,
    CONFIG_PROTOCOL,
    CONFIG_RAW_PIPELINE,
    CONFIG_STREAM_FORMAT,
    CONFIG_USERNAME,
    CONFIG_WIDTH,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_AUDIO_PIPELINE,
    DEFAULT_CODEC,
    ENV_GSTREAMER_PATH,
    LOGLEVEL_CONVERTER,
    PIXEL_FORMAT,
    STREAM_FORMAT_MAP,
)
from .pipeline import AbstractPipeline, BasePipeline, JetsonPipeline, RawPipeline

if TYPE_CHECKING:
    from viseron.components.gstreamer.camera import Camera


class Stream:
    """Represents a stream of frames from a camera."""

    def __init__(self, config, camera: Camera, camera_identifier) -> None:
        self._logger = logging.getLogger(__name__ + "." + camera_identifier)
        self._logger.addFilter(
            UnhelpfullLogFilter(config[CONFIG_GSTREAMER_RECOVERABLE_ERRORS])
        )
        self._config = config
        self._camera_identifier = camera_identifier

        self._camera: Camera = camera

        self._pipe = None
        self._segment_process = None
        self._log_pipe = LogPipe(
            self._logger, LOGLEVEL_CONVERTER[config[CONFIG_GSTREAMER_LOGLEVEL]]
        )

        self._ffprobe_log_pipe = LogPipe(
            self._logger, FFPROBE_LOGLEVELS[config[CONFIG_FFPROBE_LOGLEVEL]]
        )
        self._ffprobe_timeout = FFPROBE_TIMEOUT

        self._output_stream_config = config

        stream_codec = None
        stream_audio_codec = None
        # If any of the parameters are unset we need to fetch them using FFprobe
        if (
            not self._output_stream_config[CONFIG_WIDTH]
            or not self._output_stream_config[CONFIG_HEIGHT]
            or not self._output_stream_config[CONFIG_FPS]
            or not self._output_stream_config[CONFIG_CODEC]
            or self._output_stream_config[CONFIG_CODEC] == DEFAULT_CODEC
            or (
                self._output_stream_config[CONFIG_AUDIO_CODEC] == DEFAULT_AUDIO_CODEC
                and self._output_stream_config[CONFIG_AUDIO_PIPELINE]
                == DEFAULT_AUDIO_PIPELINE
            )
        ):
            (
                width,
                height,
                fps,
                stream_codec,
                stream_audio_codec,
            ) = self.get_stream_information(self.output_stream_url)

        self.width = (
            self._output_stream_config[CONFIG_WIDTH]
            if self._output_stream_config[CONFIG_WIDTH]
            else width
        )
        self.height = (
            self._output_stream_config[CONFIG_HEIGHT]
            if self._output_stream_config[CONFIG_HEIGHT]
            else height
        )
        self.fps = (
            self._output_stream_config[CONFIG_FPS]
            if self._output_stream_config[CONFIG_FPS]
            else fps
        )
        self.stream_codec = stream_codec
        self.stream_audio_codec = stream_audio_codec
        self._output_fps = self.fps

        if self.width and self.height and self.fps:
            pass
        else:
            raise StreamInformationError(self.width, self.height, self.fps)

        self.create_symlink(self.alias)
        self.create_symlink(self.segments_alias)

        self._pixel_format = PIXEL_FORMAT.lower()
        self._color_plane_width = self.width
        self._color_plane_height = int(self.height * 1.5)
        self._frame_bytes_size = int(self.width * self.height * 1.5)

        # For now only the Nano has a specific pipeline
        self._pipeline: AbstractPipeline
        if self._config[CONFIG_RAW_PIPELINE]:
            self._pipeline = RawPipeline(config)
        elif os.getenv(ENV_RASPBERRYPI3) == "true":
            self._pipeline = BasePipeline(config, self, camera_identifier)
        elif os.getenv(ENV_RASPBERRYPI4) == "true":
            self._pipeline = BasePipeline(config, self, camera_identifier)
        elif os.getenv(ENV_JETSON_NANO) == "true":
            self._pipeline = JetsonPipeline(config, self, camera_identifier)
        elif os.getenv(ENV_CUDA_SUPPORTED) == "true":
            self._pipeline = BasePipeline(config, self, camera_identifier)
        else:
            self._pipeline = BasePipeline(config, self, camera_identifier)

    @property
    def stream_url(self) -> str:
        """Return stream url."""
        auth = ""
        if self._config[CONFIG_USERNAME] and self._config[CONFIG_PASSWORD]:
            auth = f"{self._config[CONFIG_USERNAME]}:{self._config[CONFIG_PASSWORD]}@"

        protocol = (
            self._config[CONFIG_PROTOCOL]
            if self._config[CONFIG_PROTOCOL]
            else STREAM_FORMAT_MAP[self._config[CONFIG_STREAM_FORMAT]]["protocol"]
        )
        return (
            f"{protocol}://"
            f"{auth}"
            f"{self._config[CONFIG_HOST]}:{self._config[CONFIG_PORT]}"
            f"{self._config[CONFIG_PATH]}"
        )

    @property
    def output_stream_url(self) -> str:
        """Return output stream url."""
        auth = ""
        if self._config[CONFIG_USERNAME] and self._config[CONFIG_PASSWORD]:
            auth = f"{self._config[CONFIG_USERNAME]}:{self._config[CONFIG_PASSWORD]}@"

        protocol = (
            self._output_stream_config[CONFIG_PROTOCOL]
            if self._output_stream_config[CONFIG_PROTOCOL]
            else STREAM_FORMAT_MAP[self._output_stream_config[CONFIG_STREAM_FORMAT]][
                "protocol"
            ]
        )
        return (
            f"{protocol}://"
            f"{auth}"
            f"{self._config[CONFIG_HOST]}:{self._output_stream_config[CONFIG_PORT]}"
            f"{self._output_stream_config[CONFIG_PATH]}"
        )

    @property
    def output_stream_config(self):
        """Return output stream config."""
        return self._output_stream_config

    @property
    def alias(self) -> str:
        """Return GStreamer executable alias."""
        return f"gstreamer_{self._camera_identifier}"

    @property
    def segments_alias(self) -> str:
        """Return GStreamer segments executable alias."""
        return f"gstreamer_{self._camera_identifier}_seg"

    @staticmethod
    def create_symlink(alias) -> None:
        """Create a symlink to GStreamer executable.

        This is done to know which GStreamer command belongs to which camera.
        """
        try:
            os.symlink(os.getenv(ENV_GSTREAMER_PATH), f"/home/abc/bin/{alias}")
        except FileExistsError:
            pass

    @property
    def output_fps(self):
        """Return stream output FPS."""
        return self._output_fps

    @output_fps.setter
    def output_fps(self, fps) -> None:
        self._output_fps = fps

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
            + [self._config[CONFIG_FFPROBE_LOGLEVEL]]
            + [
                "-print_format",
                "json",
                "-show_error",
                "-show_streams",
            ]
            + [stream_url]
        )
        self._logger.debug(f"FFprobe command: {' '.join(ffprobe_command)}")

        for attempt in Retrying(
            retry=retry_if_exception_type((sp.TimeoutExpired, FFprobeTimeout)),
            stop=stop_after_attempt(10),
            wait=wait_exponential(multiplier=2, min=1, max=30),
            before_sleep=before_sleep_log(self._logger, logging.ERROR),
            reraise=True,
        ):
            with attempt:
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
                    raise FFprobeTimeout(ffprobe_timeout) from error
                self._ffprobe_timeout = FFPROBE_TIMEOUT

        try:
            # Trim away any text before start of JSON object
            trimmed_stdout = stdout[stdout.find(b"{") :]
            output: dict = json.loads(trimmed_stdout)
        except json.decoder.JSONDecodeError as error:
            raise FFprobeError(
                stdout,
            ) from error

        if output.get("error", None):
            raise FFprobeError(
                output,
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
        self._logger.debug(f"Getting stream information for {stream_url}")
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

    def build_segment_command(self):
        """Return command for writing segments only from main stream.

        Only used when a substream is configured.
        """
        raise NotImplementedError

    def pipe(self):
        """Return subprocess pipe for GStreamer."""
        return sp.Popen(
            self._pipeline.build_pipeline(),
            stdout=sp.PIPE,
            stderr=self._log_pipe,
        )

    def start_pipe(self) -> None:
        """Start piping frames from GStreamer."""
        self._logger.debug(
            f"GStreamer decoder command: {' '.join(self._pipeline.build_pipeline())}"
        )

        self._pipe = self.pipe()

    def close_pipe(self) -> None:
        """Close GStreamer pipe."""
        if self._segment_process:
            self._segment_process.terminate()

        if self.poll() is not None:
            return

        self._pipe.terminate()

        try:
            self._pipe.communicate(timeout=5)
        except sp.TimeoutExpired:
            self._logger.debug("GStreamer did not terminate, killing instead.")
            self._pipe.kill()
            self._pipe.communicate()

    def poll(self):
        """Poll pipe."""
        return self._pipe.poll()

    def read(self):
        """Return a single frame from GStreamer pipe."""
        if self._pipe:
            try:
                frame_bytes = self._pipe.stdout.read(self._frame_bytes_size)
                if len(frame_bytes) == self._frame_bytes_size:
                    shared_frame = SharedFrame(
                        self._color_plane_width,
                        self._color_plane_height,
                        self._pixel_format,
                        (self.width, self.height),
                        self._camera_identifier,
                    )
                    self._camera.shared_frames.create(shared_frame, frame_bytes)
                    return shared_frame
            except Exception as err:  # pylint: disable=broad-except
                self._logger.error(f"Error reading frame from GStreamer: {err}")
        return None
