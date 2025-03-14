"""Class to interact with an FFmpeg stream."""
from __future__ import annotations

import json
import logging
import os
import subprocess as sp
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from viseron.const import (
    CAMERA_SEGMENT_DURATION,
    ENV_CUDA_SUPPORTED,
    ENV_JETSON_NANO,
    ENV_RASPBERRYPI3,
    ENV_RASPBERRYPI4,
)
from viseron.domains.camera.shared_frames import SharedFrame
from viseron.exceptions import FFprobeError, FFprobeTimeout, StreamInformationError
from viseron.helpers import escape_string
from viseron.helpers.logs import LogPipe, UnhelpfullLogFilter
from viseron.watchdog.subprocess_watchdog import RestartablePopen

from .const import (
    CAMERA_INPUT_ARGS,
    CONFIG_AUDIO_CODEC,
    CONFIG_CODEC,
    CONFIG_FFMPEG_LOGLEVEL,
    CONFIG_FFMPEG_RECOVERABLE_ERRORS,
    CONFIG_FFPROBE_LOGLEVEL,
    CONFIG_FPS,
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
    CONFIG_RECORDER,
    CONFIG_RECORDER_AUDIO_CODEC,
    CONFIG_RECORDER_AUDIO_FILTERS,
    CONFIG_RECORDER_CODEC,
    CONFIG_RECORDER_OUPTUT_ARGS,
    CONFIG_RECORDER_VIDEO_FILTERS,
    CONFIG_RTSP_TRANSPORT,
    CONFIG_STREAM_FORMAT,
    CONFIG_SUBSTREAM,
    CONFIG_USERNAME,
    CONFIG_VIDEO_FILTERS,
    CONFIG_WIDTH,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_CODEC,
    DEFAULT_FFMPEG_RECOVERABLE_ERRORS,
    DEFAULT_RECORDER_AUDIO_CODEC,
    ENV_FFMPEG_PATH,
    FFMPEG_LOGLEVELS,
    FFPROBE_LOGLEVELS,
    FFPROBE_TIMEOUT,
    HWACCEL_CUDA_DECODER_CODEC_MAP,
    HWACCEL_JETSON_NANO_DECODER_CODEC_MAP,
    HWACCEL_RPI3_DECODER_CODEC_MAP,
    HWACCEL_RPI4_DECODER_CODEC_MAP,
    STREAM_FORMAT_MAP,
)

if TYPE_CHECKING:
    from viseron.components.ffmpeg.camera import Camera


@dataclass
class StreamInformation:
    """Stream information class."""

    width: int
    height: int
    fps: int
    codec: str
    audio_codec: str | None
    url: str
    config: dict[str, Any]


class Stream:
    """Represents a stream of frames from a camera."""

    def __init__(
        self, config: dict[str, Any], camera: Camera, camera_identifier: str
    ) -> None:
        self._logger = logging.getLogger(__name__ + "." + camera_identifier)
        self._logger.addFilter(
            UnhelpfullLogFilter(
                list(  # Remove duplicates
                    set(config[CONFIG_FFMPEG_RECOVERABLE_ERRORS])
                    | set(DEFAULT_FFMPEG_RECOVERABLE_ERRORS)
                )
            )
        )
        self._config = config
        self._camera_identifier = camera_identifier

        self._camera: Camera = camera

        self._pipe: sp.Popen | None = None
        self.segment_process: RestartablePopen | None = None
        self._log_pipe: LogPipe | None = None
        self._ffprobe = FFprobe(config, camera_identifier)

        self._mainstream = self.get_stream_information(config)
        self._substream = None
        if config.get(CONFIG_SUBSTREAM, None):
            self._substream = self.get_stream_information(config[CONFIG_SUBSTREAM])

        self._output_fps = self.fps
        self._pixel_format = (
            self._substream.config[CONFIG_PIX_FMT]
            if self._substream
            else self._mainstream.config[CONFIG_PIX_FMT]
        )
        self._color_plane_width = self.width
        self._color_plane_height = int(self.height * 1.5)
        self._frame_bytes_size = int(self.width * self.height * 1.5)

        self.create_symlink(self.alias)
        self.create_symlink(self.segments_alias)

    @property
    def output_args(self):
        """Return FFmpeg output args."""
        return [
            "-f",
            "rawvideo",
            "-pix_fmt",
            self._pixel_format,
            "pipe:1",
        ]

    @property
    def alias(self) -> str:
        """Return FFmpeg executable alias."""
        return f"ffmpeg_{self._camera_identifier}"

    @property
    def segments_alias(self) -> str:
        """Return FFmpeg segments executable alias."""
        return f"ffmpeg_{self._camera_identifier}_seg"

    @staticmethod
    def create_symlink(alias) -> None:
        """Create a symlink to FFmpeg executable.

        This is done to know which FFmpeg command belongs to which camera.
        """
        path = os.getenv(ENV_FFMPEG_PATH)

        if not path:
            raise RuntimeError("FFmpeg path not set")

        try:
            os.symlink(path, f"/home/abc/bin/{alias}")
        except FileExistsError:
            pass

    @property
    def width(self) -> int:
        """Return stream width."""
        if self._substream:
            return self._substream.width
        return self._mainstream.width

    @property
    def height(self) -> int:
        """Return stream height."""
        if self._substream:
            return self._substream.height
        return self._mainstream.height

    @property
    def fps(self) -> int:
        """Return stream FPS."""
        if self._substream:
            return self._substream.fps
        return self._mainstream.fps

    @property
    def output_fps(self):
        """Return stream output FPS."""
        return self._output_fps

    @output_fps.setter
    def output_fps(self, fps) -> None:
        self._output_fps = fps

    def get_stream_url(self, stream_config: dict[str, Any]) -> str:
        """Return stream url."""
        username = self._config[CONFIG_USERNAME]
        password = self._config[CONFIG_PASSWORD]
        auth = ""
        if username is not None and password is not None:
            auth = f"{username}:{escape_string(password)}@"

        protocol = (
            stream_config[CONFIG_PROTOCOL]
            if stream_config[CONFIG_PROTOCOL]
            else STREAM_FORMAT_MAP[stream_config[CONFIG_STREAM_FORMAT]]["protocol"]
        )

        return (
            f"{protocol}://"
            f"{auth}"
            f"{self._config[CONFIG_HOST]}:{stream_config[CONFIG_PORT]}"
            f"{stream_config[CONFIG_PATH]}"
        )

    def get_stream_information(
        self, stream_config: dict[str, Any]
    ) -> StreamInformation:
        """Return stream information."""
        # If any of the parameters are unset we need to fetch them using FFprobe
        stream_url = self.get_stream_url(stream_config)
        if (
            not stream_config[CONFIG_WIDTH]
            or not stream_config[CONFIG_HEIGHT]
            or not stream_config[CONFIG_FPS]
            or not stream_config[CONFIG_CODEC]
            or stream_config[CONFIG_CODEC] == DEFAULT_CODEC
            or stream_config[CONFIG_AUDIO_CODEC] == DEFAULT_AUDIO_CODEC
        ):
            self._logger.debug(f"Getting stream information for {stream_url}")
            width, height, fps, codec, audio_codec = self._ffprobe.stream_information(
                stream_url, stream_config
            )

        width = stream_config[CONFIG_WIDTH] if stream_config[CONFIG_WIDTH] else width
        height = (
            stream_config[CONFIG_HEIGHT] if stream_config[CONFIG_HEIGHT] else height
        )
        fps = stream_config[CONFIG_FPS] if stream_config[CONFIG_FPS] else fps
        codec = (
            stream_config[CONFIG_CODEC]
            if stream_config[CONFIG_CODEC] != DEFAULT_CODEC
            else codec
        )
        audio_codec = (
            stream_config[CONFIG_AUDIO_CODEC]
            if stream_config[CONFIG_AUDIO_CODEC] != DEFAULT_AUDIO_CODEC
            else audio_codec
        )

        self._logger.debug(
            "Stream information from FFprobe: "
            f"Width: {width} "
            f"Height: {height} "
            f"FPS: {fps} "
            f"Video Codec: {codec} "
            f"Audio Codec: {audio_codec}"
        )
        if width and height and fps and codec:
            pass
        else:
            raise StreamInformationError(width, height, fps, codec)

        return StreamInformation(
            width, height, fps, codec, audio_codec, stream_url, stream_config
        )

    @staticmethod
    def get_decoder_codec(stream_config: dict[str, Any], stream_codec: str):
        """Return decoder codec set in config or from predefined codec map."""
        if stream_config[CONFIG_CODEC] and stream_config[CONFIG_CODEC] != DEFAULT_CODEC:
            return ["-c:v", stream_config[CONFIG_CODEC]]

        codec = None
        codec_map = None
        if stream_codec:
            if stream_config[CONFIG_STREAM_FORMAT] in ["rtsp", "rtmp"]:
                if os.getenv(ENV_RASPBERRYPI3) == "true":
                    codec_map = HWACCEL_RPI3_DECODER_CODEC_MAP
                elif os.getenv(ENV_RASPBERRYPI4) == "true":
                    codec_map = HWACCEL_RPI4_DECODER_CODEC_MAP
                elif os.getenv(ENV_JETSON_NANO) == "true":
                    codec_map = HWACCEL_JETSON_NANO_DECODER_CODEC_MAP
                elif os.getenv(ENV_CUDA_SUPPORTED) == "true":
                    codec_map = HWACCEL_CUDA_DECODER_CODEC_MAP
                if codec_map:
                    codec = codec_map.get(stream_codec, None)
        if codec:
            return ["-c:v", codec]
        return []

    def get_encoder_codec(self):
        """Return encoder codec set in config."""
        return ["-c:v", self._config[CONFIG_RECORDER][CONFIG_RECORDER_CODEC]]

    def stream_command(
        self, stream_config: dict[str, Any], stream_codec: str, stream_url: str
    ):
        """Return FFmpeg input stream."""
        if stream_config[CONFIG_INPUT_ARGS]:
            input_args = stream_config[CONFIG_INPUT_ARGS]
        else:
            input_args = CAMERA_INPUT_ARGS + list(
                STREAM_FORMAT_MAP[stream_config[CONFIG_STREAM_FORMAT]]["timeout_option"]
            )

        return (
            input_args
            + stream_config[CONFIG_HWACCEL_ARGS]
            + self.get_decoder_codec(stream_config, stream_codec)
            + (
                ["-rtsp_transport", stream_config[CONFIG_RTSP_TRANSPORT]]
                if stream_config[CONFIG_STREAM_FORMAT] == "rtsp"
                else []
            )
            + ["-i", stream_url]
        )

    def get_encoder_audio_codec(
        self,
        stream_audio_codec: str | None,
    ) -> list[str]:
        """Return audio codec used for saving segments."""
        if (
            self._config[CONFIG_RECORDER][CONFIG_RECORDER_AUDIO_CODEC]
            and self._config[CONFIG_RECORDER][CONFIG_RECORDER_AUDIO_CODEC]
            != DEFAULT_RECORDER_AUDIO_CODEC
        ):
            return [
                "-c:a",
                self._config[CONFIG_RECORDER][CONFIG_RECORDER_AUDIO_CODEC],
            ]

        if self._config[CONFIG_RECORDER][CONFIG_RECORDER_AUDIO_CODEC] is None:
            return ["-an"]

        if stream_audio_codec in [
            "pcm_alaw",
            "pcm_mulaw",
        ]:
            self._logger.warning(
                f"Container mp4 does not support {stream_audio_codec} audio "
                "codec. Audio will be transcoded as aac."
            )
            return ["-c:a", "aac"]

        if stream_audio_codec:
            return ["-c:a", "copy"]

        return ["-an"]

    def recorder_video_filter_args(self) -> list[str] | list:
        """Return video filter arguments."""
        if filters := self._config[CONFIG_RECORDER][CONFIG_RECORDER_VIDEO_FILTERS]:
            return [
                "-vf",
                ",".join(filters),
            ]
        return []

    def recorder_audio_filter_args(self) -> list[str] | list:
        """Return audio filter arguments."""
        if filters := self._config[CONFIG_RECORDER][CONFIG_RECORDER_AUDIO_FILTERS]:
            return [
                "-af",
                ",".join(filters),
            ]
        return []

    def segment_args(self):
        """Generate FFmpeg segment args."""
        return (
            [
                "-f",
                "hls",
                "-hls_time",
                str(CAMERA_SEGMENT_DURATION),
                "-hls_segment_type",
                "fmp4",
                "-hls_list_size",
                "10",
                "-hls_flags",
                "program_date_time+delete_segments",
                "-strftime",
                "1",
                "-hls_segment_filename",
                os.path.join(
                    self._camera.temp_segments_folder,
                    "%s.m4s",
                ),
            ]
            + self.get_encoder_codec()
            + self.recorder_video_filter_args()
            + self.get_encoder_audio_codec(self._mainstream.audio_codec)
            + self.recorder_audio_filter_args()
            + self._camera.config[CONFIG_RECORDER][CONFIG_RECORDER_OUPTUT_ARGS]
            + [
                os.path.join(
                    self._camera.temp_segments_folder,
                    "index.m3u8",
                ),
            ]
        )

    def filter_args(self):
        """Return filter arguments."""
        filters = self._config[CONFIG_VIDEO_FILTERS].copy()
        if self.output_fps < self.fps:
            filters.append(f"fps={self.output_fps}")

        if filters:
            return [
                "-vf",
                ",".join(filters),
            ]
        return []

    def build_segment_command(self):
        """Return command for writing segments only from main stream.

        Only used when a substream is configured.
        """
        if self._config[CONFIG_RAW_COMMAND]:
            return self._config[CONFIG_RAW_COMMAND].split(" ")

        stream_input_command = self.stream_command(
            self._config, self._mainstream.codec, self._mainstream.url
        )
        return (
            [self.segments_alias]
            + self._config[CONFIG_GLOBAL_ARGS]
            + ["-loglevel"]
            + [self._config[CONFIG_FFMPEG_LOGLEVEL]]
            + stream_input_command
            + self.segment_args()
        )

    def build_command(self):
        """Return full FFmpeg command."""
        if self._substream:
            if self._config[CONFIG_SUBSTREAM][CONFIG_RAW_COMMAND]:
                return self._config[CONFIG_SUBSTREAM][CONFIG_RAW_COMMAND].split(" ")
            stream_input_command = self.stream_command(
                self._substream.config,
                self._substream.codec,
                self._substream.url,
            )
            camera_segment_args = []
        else:
            if self._config[CONFIG_RAW_COMMAND]:
                return self._config[CONFIG_RAW_COMMAND].split(" ")
            stream_input_command = self.stream_command(
                self._mainstream.config,
                self._mainstream.codec,
                self._mainstream.url,
            )
            camera_segment_args = self.segment_args()

        return (
            [self.alias]
            + self._config[CONFIG_GLOBAL_ARGS]
            + ["-loglevel"]
            + [self._config[CONFIG_FFMPEG_LOGLEVEL]]
            + stream_input_command
            + camera_segment_args
            + self.filter_args()
            + self.output_args
        )

    def pipe(self):
        """Return subprocess pipe for FFmpeg."""
        try:
            if self._log_pipe:
                self._log_pipe.close()
                self._log_pipe = None
        except OSError as error:
            self._logger.error("Failed to close log pipe: %s", error)

        self._log_pipe = LogPipe(
            self._logger, FFMPEG_LOGLEVELS[self._config[CONFIG_FFMPEG_LOGLEVEL]]
        )

        if self._config.get(CONFIG_SUBSTREAM, None):
            self.segment_process = RestartablePopen(
                self.build_segment_command(),
                name=f"viseron.camera.{self._camera.identifier}.segments",
                stdout=sp.PIPE,
                stderr=self._log_pipe,
            )

        return sp.Popen(  # type: ignore[call-overload]
            self.build_command(),
            stdout=sp.PIPE,
            stderr=self._log_pipe,
        )

    def start_pipe(self) -> None:
        """Start piping frames from FFmpeg."""
        self._logger.debug(f"FFmpeg decoder command: {' '.join(self.build_command())}")
        if self._config.get(CONFIG_SUBSTREAM, None):
            self._logger.debug(
                f"FFmpeg segments command: {' '.join(self.build_segment_command())}"
            )

        self._pipe = self.pipe()

    def close_pipe(self) -> None:
        """Close FFmpeg pipe."""
        if self.segment_process:
            self.segment_process.terminate()

        if self._pipe:
            try:
                self._pipe.terminate()
                try:
                    self._pipe.communicate(timeout=5)
                except sp.TimeoutExpired:
                    self._logger.debug("FFmpeg did not terminate, killing instead.")
                    self._pipe.kill()
                    self._pipe.communicate()
            except AttributeError as error:
                self._logger.error("Failed to close pipe: %s", error)

        try:
            if self._log_pipe:
                self._log_pipe.close()
                self._log_pipe = None
        except OSError as error:
            self._logger.error("Failed to close log pipe: %s", error)

    def poll(self):
        """Poll pipe."""
        if self._pipe:
            return self._pipe.poll()

    def read(self):
        """Return a single frame from FFmpeg pipe."""
        try:
            if self._pipe and self._pipe.stdout:
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
            self._logger.error(f"Error reading frame from pipe: {err}")
        return None

    def record_only(self):
        """Record only the stream."""
        self._logger.debug(f"Recording only stream: {' '.join(self.build_command())}")
        try:
            if self._log_pipe:
                self._log_pipe.close()
                self._log_pipe = None
        except OSError as error:
            self._logger.error("Failed to close log pipe: %s", error)

        self._log_pipe = LogPipe(
            self._logger, FFMPEG_LOGLEVELS[self._config[CONFIG_FFMPEG_LOGLEVEL]]
        )

        self.segment_process = RestartablePopen(
            self.build_segment_command(),
            name=f"viseron.camera.{self._camera.identifier}.segments",
            stdout=sp.PIPE,
            stderr=self._log_pipe,
        )


class FFprobe:
    """FFprobe wrapper class."""

    def __init__(self, config: dict[str, Any], camera_identifier: str) -> None:
        self._logger = logging.getLogger(__name__ + "." + camera_identifier)
        self._config = config
        self._ffprobe_timeout = FFPROBE_TIMEOUT

    def stream_information(
        self, stream_url: str, stream_config: dict[str, Any]
    ) -> tuple[int, int, int, str | None, str | None]:
        """Return stream information using FFprobe."""
        width, height, fps, codec, audio_codec = 0, 0, 0, None, None
        streams = self.run_ffprobe(stream_url, stream_config)

        video_stream: dict[str, Any] | None = None
        audio_stream: dict[str, Any] | None = None
        for stream in streams["streams"]:
            if video_stream and audio_stream:
                break
            if stream["codec_type"] == "video":
                video_stream = stream
            elif stream["codec_type"] == "audio":
                audio_stream = stream

        if audio_stream:
            audio_codec = audio_stream.get("codec_name", None)

        if video_stream is None:
            return (width, height, fps, codec, audio_codec)

        try:
            numerator = int(video_stream["avg_frame_rate"].split("/")[0])
            denominator = int(video_stream["avg_frame_rate"].split("/")[1])
        except KeyError:
            return (width, height, fps, codec, audio_codec)

        try:
            fps = int(numerator / denominator)
        except ZeroDivisionError:
            pass

        width = video_stream.get("width", 0)
        height = video_stream.get("height", 0)
        codec = video_stream.get("codec_name", None)

        return (width, height, fps, codec, audio_codec)

    def run_ffprobe(
        self,
        stream_url: str,
        stream_config: dict[str, Any],
    ) -> dict[str, Any]:
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
                "-show_entries",
                "stream=codec_type,codec_name,width,height,avg_frame_rate",
            ]
            + (
                ["-rtsp_transport", stream_config[CONFIG_RTSP_TRANSPORT]]
                if stream_config[CONFIG_STREAM_FORMAT] == "rtsp"
                else []
            )
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
                log_pipe = LogPipe(
                    self._logger,
                    FFPROBE_LOGLEVELS[self._config[CONFIG_FFPROBE_LOGLEVEL]],
                )
                pipe = sp.Popen(  # type: ignore[call-overload]
                    ffprobe_command,
                    stdout=sp.PIPE,
                    stderr=log_pipe,
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
                finally:
                    log_pipe.close()
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
