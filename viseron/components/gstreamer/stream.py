"""Class to interact with a GStreamer stream."""
from __future__ import annotations

import datetime
import logging
import multiprocessing as mp
import os
import time
from multiprocessing.synchronize import Event as EventClass
from typing import TYPE_CHECKING, Any

import gi
import setproctitle

from viseron.components.ffmpeg.stream import FFprobe, Stream as FFmpegStream
from viseron.const import (
    ENV_CUDA_SUPPORTED,
    ENV_JETSON_NANO,
    ENV_RASPBERRYPI3,
    ENV_RASPBERRYPI4,
)
from viseron.domains.camera.shared_frames import SharedFrame
from viseron.helpers import pop_if_full
from viseron.helpers.logs import UnhelpfullLogFilter
from viseron.watchdog.process_watchdog import RestartableProcess

from .const import (
    CONFIG_GSTREAMER_LOGLEVEL,
    CONFIG_GSTREAMER_RECOVERABLE_ERRORS,
    CONFIG_LOGLEVEL_TO_GSTREAMER,
    CONFIG_RAW_PIPELINE,
    ENV_GSTREAMER_PATH,
    GSTREAMER_LOGLEVEL_TO_PYTHON,
    PIXEL_FORMAT,
)
from .pipeline import AbstractPipeline, BasePipeline, JetsonPipeline, RawPipeline

if TYPE_CHECKING:
    from viseron.components.gstreamer.camera import Camera

# pylint: disable=useless-suppression
# pylint: disable=wrong-import-position,wrong-import-order,no-name-in-module
gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import (  # pyright: ignore[reportMissingImports] # noqa: E402
    GLib,
    Gst,
    GstApp,
)

_ = GstApp
# pylint: enable=wrong-import-position,wrong-import-order,no-name-in-module
# pylint: enable=useless-suppression


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

        self._ffprobe = FFprobe(config, camera_identifier)

        self._mainstream = self.get_stream_information(config)
        self._substream = None  # Substream is not implemented for GStreamer

        self._logger_gstreamer = logging.getLogger(f"{self._logger.name}.gstreamer")
        self._process_frames_proc: RestartableProcess | None = None
        self._frame_queue: mp.Queue[bytes] = mp.Queue(maxsize=1)
        self._process_frames_proc_exit = mp.Event()

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

    def on_new_sample(self, app_sink: GstApp.AppSink) -> Gst.FlowReturn:
        """Process new buffer from appsink."""
        sample = app_sink.get_last_sample()

        if not isinstance(sample, Gst.Sample):
            self._logger.debug("Did not get sample from appsink")
            return Gst.FlowReturn.ERROR

        buffer: Gst.Buffer = sample.get_buffer()
        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            self._logger.debug("Could not map buffer data")
            return Gst.FlowReturn.ERROR

        pop_if_full(self._frame_queue, map_info.data)

        buffer.unmap(map_info)
        return Gst.FlowReturn.OK

    def on_format_location(self, _splitmux, _fragment_id, _udata) -> str:
        """Return the location of the next segment."""
        timestamp = int(datetime.datetime.utcnow().timestamp())
        return os.path.join(
            self._camera.temp_segments_folder,
            f"{timestamp}.{self._camera.extension}",
        )

    def on_gst_log_message(
        self,
        category: Gst.DebugCategory,
        level: Gst.DebugLevel,
        file: str,
        function: str,
        line: int,
        _object,
        message: Gst.DebugMessage,
        *_user_data: None,
    ):
        """Handle GStreamer log messages."""
        self._logger_gstreamer.log(
            GSTREAMER_LOGLEVEL_TO_PYTHON[level],
            "%s %s:%s:%s: %s",
            category.get_name(),
            file,
            line,
            function,
            message.get(),
        )

    def run_gstreamer(self, process_frames_proc_exit: EventClass) -> None:
        """Run GStreamer in a subprocess."""
        setproctitle.setproctitle(self.alias)
        mainloop = GLib.MainLoop()

        Gst.init(None)
        # Remove logging to stderr
        Gst.debug_remove_log_function(None)
        Gst.debug_set_default_threshold(
            CONFIG_LOGLEVEL_TO_GSTREAMER[self._config[CONFIG_GSTREAMER_LOGLEVEL]]
        )
        Gst.debug_add_log_function(self.on_gst_log_message, None)

        gst_pipeline = Gst.parse_launch(" ".join(self._pipeline.build_pipeline()))
        appsink = gst_pipeline.get_by_name(
            "sink",
        )
        gst_pipeline.set_state(Gst.State.PLAYING)
        appsink.connect("new-sample", self.on_new_sample)
        mux = gst_pipeline.get_by_name("mux")
        mux.connect("format-location", self.on_format_location, None)

        while not process_frames_proc_exit.is_set():
            time.sleep(1)

        gst_pipeline.set_state(Gst.State.NULL)
        mainloop.quit()

    def start_pipe(self) -> None:
        """Start piping frames from GStreamer."""
        self._logger.debug(
            f"GStreamer decoder command: {' '.join(self._pipeline.build_pipeline())}"
        )

        self._process_frames_proc = RestartableProcess(
            target=self.run_gstreamer,
            args=(self._process_frames_proc_exit,),
            name=self.alias,
            daemon=True,
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
