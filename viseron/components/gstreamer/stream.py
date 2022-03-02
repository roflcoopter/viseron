"""Class to interact with an FFmpeog stream."""
from __future__ import annotations

import json
import logging
import os
import subprocess as sp

from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from viseron.const import (
    ENV_CUDA_SUPPORTED,
    ENV_JETSON_NANO,
    ENV_RASPBERRYPI3,
    ENV_RASPBERRYPI4,
)
from viseron.domains.camera.shared_frames import SharedFrame
from viseron.exceptions import FFprobeError, FFprobeTimeout, StreamInformationError
from viseron.helpers.logs import FFmpegFilter, LogPipe
from viseron.helpers.subprocess import Popen
from viseron.watchdog.subprocess_watchdog import RestartablePopen

from .const import (
    COMPONENT,
    CONFIG_AUDIO_CODEC,
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
    CONFIG_STREAM_FORMAT,
    CONFIG_SUBSTREAM,
    CONFIG_USERNAME,
    CONFIG_WIDTH,
    ENV_GSTREAMER_PATH,
    FFPROBE_TIMEOUT,
    GSTREAMER_LOG_LEVELS,
    PIXEL_FORMAT,
    STREAM_FORMAT_MAP,
)
from .pipeline import BasePipeline, JetsonPipeline


class Stream:
    """Represents a stream of frames from a camera."""

    def __init__(self, vis, config, camera_identifier):
        self._logger = logging.getLogger(__name__ + "." + camera_identifier)
        self._logger.addFilter(
            FFmpegFilter(config[CONFIG_GSTREAMER_RECOVERABLE_ERRORS])
        )
        self._config = config
        self._camera_identifier = camera_identifier

        self._camera = vis.data[COMPONENT][camera_identifier]
        self._recorder = vis.data[COMPONENT][camera_identifier].recorder

        self._pipe = None
        self._segment_process = None
        self._log_pipe = LogPipe(
            self._logger, GSTREAMER_LOG_LEVELS[config[CONFIG_GSTREAMER_LOGLEVEL]]
        )

        self._ffprobe_log_pipe = LogPipe(
            self._logger, GSTREAMER_LOG_LEVELS[config[CONFIG_FFPROBE_LOGLEVEL]]
        )
        self._ffprobe_timeout = FFPROBE_TIMEOUT

        self._output_stream_config = config
        if config.get(CONFIG_SUBSTREAM, None):
            self._output_stream_config = config[CONFIG_SUBSTREAM]

        stream_codec = None
        stream_audio_codec = None
        # If any of the parameters are unset we need to fetch them using FFprobe
        if (
            not self._output_stream_config[CONFIG_WIDTH]
            or not self._output_stream_config[CONFIG_HEIGHT]
            or not self._output_stream_config[CONFIG_FPS]
            or not self._output_stream_config[CONFIG_CODEC]
            or self._output_stream_config[CONFIG_AUDIO_CODEC] == "unset"
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

        self.create_symlink()

        self._pixel_format = PIXEL_FORMAT.lower()
        self._color_plane_width = self.width
        self._color_plane_height = int(self.height * 1.5)
        self._frame_bytes_size = int(self.width * self.height * 1.5)

        # For now only the Nano has a specific pipeline
        if os.getenv(ENV_RASPBERRYPI3) == "true":
            self._pipeline = BasePipeline(vis, config, self, camera_identifier)
        elif os.getenv(ENV_RASPBERRYPI4) == "true":
            self._pipeline = BasePipeline(vis, config, self, camera_identifier)
        elif os.getenv(ENV_JETSON_NANO) == "true":
            self._pipeline = JetsonPipeline(vis, config, self, camera_identifier)
        elif os.getenv(ENV_CUDA_SUPPORTED) == "true":
            self._pipeline = BasePipeline(vis, config, self, camera_identifier)
        else:
            self._pipeline = BasePipeline(vis, config, self, camera_identifier)

    @property
    def stream_url(self):
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
    def output_stream_url(self):
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
    def alias(self):
        """Return GStreamer executable alias."""
        return f"gstreamer_{self._camera_identifier}"

    def create_symlink(self):
        """Create a symlink to GStreamer executable.

        This is done to know which GStreamer command belongs to which camera.
        """
        try:
            os.symlink(os.getenv(ENV_GSTREAMER_PATH), f"/home/abc/bin/{self.alias}")
        except FileExistsError:
            pass

    @property
    def output_fps(self):
        """Return stream output FPS."""
        return self._output_fps

    @output_fps.setter
    def output_fps(self, fps):
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

        for attempt in Retrying(
            retry=retry_if_exception_type((sp.TimeoutExpired, FFprobeTimeout)),
            stop=stop_after_attempt(10),
            wait=wait_exponential(multiplier=2, min=1, max=30),
            before_sleep=before_sleep_log(self._logger, logging.ERROR),
            reraise=True,
        ):
            with attempt:
                pipe = Popen(  # type: ignore
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

    def build_segment_command(self):
        """Return command for writing segments only from main stream.

        Only used when a substream is configured.
        """
        raise NotImplementedError

    def pipe(self):
        """Return subprocess pipe for GStreamer."""
        if self._config.get(CONFIG_SUBSTREAM, None):
            self._segment_process = RestartablePopen(
                self.build_segment_command(),
                stdout=sp.PIPE,
                stderr=self._log_pipe,
            )

        return Popen(
            self._pipeline.build_pipeline(),
            stdout=sp.PIPE,
            stderr=self._log_pipe,
        )

    def start_pipe(self):
        """Start piping frames from GStreamer."""
        self._logger.debug(
            f"GStreamer decoder command: {' '.join(self._pipeline.build_pipeline())}"
        )
        if self._config.get(CONFIG_SUBSTREAM, None):
            self._logger.debug(
                f"GStreamer segments command: {' '.join(self.build_segment_command())}"
            )

        self._pipe = self.pipe()

    def close_pipe(self):
        """Close GStreamer pipe."""
        self._pipe.terminate()
        if self._segment_process:
            self._segment_process.terminate()
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
