"""Class to interact with an FFmpeog stream."""
from __future__ import annotations

import logging
import os
import subprocess as sp
from typing import TYPE_CHECKING, Any

from viseron.components.ffmpeg.stream import FFprobe, Stream as FFmpegStream
from viseron.const import (
    ENV_CUDA_SUPPORTED,
    ENV_JETSON_NANO,
    ENV_RASPBERRYPI3,
    ENV_RASPBERRYPI4,
)
from viseron.helpers.logs import LogPipe, UnhelpfullLogFilter

from .const import (
    CONFIG_GSTREAMER_LOGLEVEL,
    CONFIG_GSTREAMER_RECOVERABLE_ERRORS,
    CONFIG_RAW_PIPELINE,
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
        self, config: dict[str, Any], camera: Camera, camera_identifier: str
    ) -> None:
        self._logger = logging.getLogger(__name__ + "." + camera_identifier)
        self._logger.addFilter(
            UnhelpfullLogFilter(config[CONFIG_GSTREAMER_RECOVERABLE_ERRORS])
        )
        self._config = config
        self._camera_identifier = camera_identifier

        self._camera: Camera = camera  # type: ignore[assignment]

        self._pipe: sp.Popen | None = None
        self._log_pipe = LogPipe(
            self._logger, LOGLEVEL_CONVERTER[config[CONFIG_GSTREAMER_LOGLEVEL]]
        )

        self._ffprobe = FFprobe(config, camera_identifier)

        self._mainstream = self.get_stream_information(config)
        self._substream = None  # Substream is not implemented for GStreamer

        self._output_fps = self.fps
        self._pixel_format = PIXEL_FORMAT.lower()
        self._color_plane_width = self.width
        self._color_plane_height = int(self.height * 1.5)
        self._frame_bytes_size = int(self.width * self.height * 1.5)

        self.create_symlink(self.alias)
        self.create_symlink(self.segments_alias)

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
    def mainstream(self):
        """Return the main stream."""
        return self._mainstream

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
