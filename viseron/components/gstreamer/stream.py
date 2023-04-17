"""Class to interact with an FFmpeog stream."""
from __future__ import annotations

import logging
import os
import subprocess as sp
from typing import TYPE_CHECKING

from viseron.components.ffmpeg.const import FFPROBE_LOGLEVELS, FFPROBE_TIMEOUT
from viseron.components.ffmpeg.stream import Stream as FFmpegStream
from viseron.const import (
    ENV_CUDA_SUPPORTED,
    ENV_JETSON_NANO,
    ENV_RASPBERRYPI3,
    ENV_RASPBERRYPI4,
)
from viseron.exceptions import StreamInformationError
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
    CONFIG_RAW_PIPELINE,
    CONFIG_WIDTH,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_AUDIO_PIPELINE,
    DEFAULT_CODEC,
    ENV_GSTREAMER_PATH,
    LOGLEVEL_CONVERTER,
    PIXEL_FORMAT,
)
from .pipeline import AbstractPipeline, BasePipeline, JetsonPipeline, RawPipeline

if TYPE_CHECKING:
    from viseron.components.gstreamer.camera import Camera


class Stream(FFmpegStream):
    """Represents a stream of frames from a camera.

    Inherits most of its functionality from the FFmpeg Stream class.
    """

    def __init__(  # pylint: disable=super-init-not-called
        self, config, camera: Camera, camera_identifier
    ) -> None:
        self._logger = logging.getLogger(__name__ + "." + camera_identifier)
        self._logger.addFilter(
            UnhelpfullLogFilter(config[CONFIG_GSTREAMER_RECOVERABLE_ERRORS])
        )
        self._config = config
        self._camera_identifier = camera_identifier

        self._camera: Camera = camera  # type: ignore[assignment]

        self._pipe = None
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

        if (
            self.width
            and self.height
            and self.fps
            and (stream_codec or config[CONFIG_CODEC])
        ):
            pass
        else:
            raise StreamInformationError(
                self.width, self.height, self.fps, stream_codec
            )

        self.stream_codec = stream_codec
        self.stream_audio_codec = stream_audio_codec
        self._output_fps = self.fps

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
        path = os.getenv(ENV_GSTREAMER_PATH)

        if not path:
            raise RuntimeError("GStreamer path not set")

        try:
            os.symlink(path, f"/home/abc/bin/{alias}")
        except FileExistsError:
            pass

    def build_segment_command(self):
        """Return command for writing segments only from main stream.

        Only used when a substream is configured.
        """
        raise NotImplementedError

    def pipe(self):
        """Return subprocess pipe for GStreamer."""
        return sp.Popen(  # type: ignore[call-overload]
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
        if not self._pipe:
            self._logger.error("No pipe to close")
            return

        try:
            self._pipe.terminate()
            try:
                self._pipe.communicate(timeout=5)
            except sp.TimeoutExpired:
                self._logger.debug("GStreamer did not terminate, killing instead.")
                self._pipe.kill()
                self._pipe.communicate()
        except AttributeError as error:
            self._logger.error("Failed to close pipe: %s", error)
