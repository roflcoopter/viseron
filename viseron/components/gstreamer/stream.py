"""Class to interact with a GStreamer stream."""

# pyright: reportMissingModuleSource=false
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from viseron.components.ffmpeg.stream import FFprobe, Stream as FFmpegStream
from viseron.const import (
    ENV_CUDA_SUPPORTED,
    ENV_JETSON_NANO,
    ENV_RASPBERRYPI3,
    ENV_RASPBERRYPI4,
    ENV_RASPBERRYPI5,
)
from viseron.domains.camera.shared_frames import SharedFrame
from viseron.helpers import pop_if_full
from viseron.helpers.child_process_context import (
    CHILD_PROCESS_START_METHOD,
    get_child_process_context,
)
from viseron.helpers.logs import SensitiveInformationFilter, UnhelpfullLogFilter
from viseron.watchdog.process_watchdog import RestartableProcess

from .const import (
    CONFIG_GSTREAMER_LOGLEVEL,
    CONFIG_GSTREAMER_RECOVERABLE_ERRORS,
    CONFIG_RAW_PIPELINE,
    ENV_GSTREAMER_PATH,
    PIXEL_FORMAT,
)
from .gst_process import GstProcessConfig, run_gstreamer
from .pipeline import AbstractPipeline, BasePipeline, JetsonPipeline, RawPipeline

if TYPE_CHECKING:
    import multiprocessing as mp

    from viseron.components.gstreamer.camera import Camera


class Stream(FFmpegStream):
    """Represents a stream of frames from a camera.

    Inherits most of its functionality from the FFmpeg Stream class.
    """

    def __init__(  # pylint: disable=super-init-not-called
        self,
        config: dict[str, Any],
        camera: Camera,
        camera_identifier: str,
        attempt: int = 1,
    ) -> None:
        self._logger = logging.getLogger(__name__ + "." + camera_identifier)
        self._logger.addFilter(
            UnhelpfullLogFilter(config[CONFIG_GSTREAMER_RECOVERABLE_ERRORS])
        )
        self._config = config
        self._camera_identifier = camera_identifier

        self._camera: Camera = camera  # type: ignore[assignment]

        self._ffprobe = FFprobe(config, camera_identifier, attempt)

        self._mainstream = self.get_stream_information(config)
        self._substream = None  # Substream is not implemented for GStreamer

        self._logger_gstreamer = logging.getLogger(f"{self._logger.name}.gstreamer")
        self._process_frames_proc: RestartableProcess | None = None
        self._mp_context = get_child_process_context()
        self._frame_queue: mp.Queue[bytes] = self._mp_context.Queue(maxsize=1)
        self._process_frames_proc_exit = self._mp_context.Event()

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
            self._pipeline = BasePipeline(config, self, camera)
        elif os.getenv(ENV_RASPBERRYPI4) == "true":
            self._pipeline = BasePipeline(config, self, camera)
        elif os.getenv(ENV_RASPBERRYPI5) == "true":
            self._pipeline = BasePipeline(config, self, camera)
        elif os.getenv(ENV_JETSON_NANO) == "true":
            self._pipeline = JetsonPipeline(config, self, camera)
        elif os.getenv(ENV_CUDA_SUPPORTED) == "true":
            self._pipeline = BasePipeline(config, self, camera)
        else:
            self._pipeline = BasePipeline(config, self, camera)

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

    def start_pipe(self) -> None:
        """Start piping frames from GStreamer."""
        pipeline = " ".join(self._pipeline.build_pipeline())
        self._logger.debug(f"GStreamer decoder command: {pipeline}")

        gst_config = GstProcessConfig(
            camera_identifier=self._camera_identifier,
            alias=self.alias,
            pipeline=pipeline,
            gst_loglevel=self._config[CONFIG_GSTREAMER_LOGLEVEL],
            temp_segments_folder=self._camera.temp_segments_folder,
            extension=self._camera.extension,
            sensitive_strings=tuple(SensitiveInformationFilter.sensitive_strings),
            log_level=logging.getLogger().level,
        )

        self._process_frames_proc = RestartableProcess(
            target=run_gstreamer,
            args=(
                gst_config,
                self._frame_queue,
                self._process_frames_proc_exit,
            ),
            name=self.alias,
            daemon=True,
            context=CHILD_PROCESS_START_METHOD,
        )
        self._process_frames_proc_exit.clear()
        self._process_frames_proc.start()

    def close_pipe(self) -> None:
        """Close GStreamer pipe."""
        if not self._process_frames_proc:
            self._logger.error("No pipeline to close")
            return

        self._logger.debug(f"Sending exit event to {self.alias}")
        self._process_frames_proc_exit.set()
        self._process_frames_proc.join(5)
        self._process_frames_proc.terminate()
        self._process_frames_proc.kill()
        pop_if_full(self._frame_queue, None)
        self._logger.debug(f"{self.alias} exited")

    def poll(self) -> int | None:
        """Mimic Popen poll."""
        if self._process_frames_proc:
            return self._process_frames_proc.exitcode
        return None

    def read(self) -> SharedFrame | None:
        """Return a single frame from Gst buffer."""
        try:
            if self._process_frames_proc:
                frame_bytes = self._frame_queue.get()
                if self._process_frames_proc_exit.is_set():
                    return None

                if frame_bytes and len(frame_bytes) == self._frame_bytes_size:
                    return SharedFrame(
                        frame_bytes,
                        self._color_plane_width,
                        self._color_plane_height,
                        self._pixel_format,
                        (self.width, self.height),
                        self._camera_identifier,
                    )
        except Exception as err:  # pylint: disable=broad-except
            self._logger.error(f"Error reading frame from pipe: {err}")
        return None
