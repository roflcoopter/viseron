"""GStreamer pipeline, executed in a child process.

Entrypoint of the GStreamer child process. Like the ffmpeg frame reader, it takes
only plain data so the child can be created with the forkserver start method instead
of fork to reduce memory usage.
"""

from __future__ import annotations

import datetime
import logging
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import gi
import setproctitle

from viseron.helpers import pop_if_full
from viseron.helpers.logs import enable_child_logging

from .const import CONFIG_LOGLEVEL_TO_GSTREAMER, GSTREAMER_LOGLEVEL_TO_PYTHON

# pylint: disable=useless-suppression
# pylint: disable=wrong-import-position,wrong-import-order,no-name-in-module
gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import GLib, Gst, GstApp  # noqa: E402

# pylint: enable=useless-suppression
# pylint: enable=wrong-import-position,wrong-import-order,no-name-in-module

if TYPE_CHECKING:
    from multiprocessing import Queue
    from multiprocessing.synchronize import Event


@dataclass(frozen=True)
class GstProcessConfig:
    """Everything the GStreamer child process needs, as plain picklable data."""

    camera_identifier: str
    alias: str
    pipeline: str
    gst_loglevel: str
    temp_segments_folder: str
    extension: str
    sensitive_strings: tuple[str, ...]
    log_level: int


def segment_location(config: GstProcessConfig) -> str:
    """Return the location of the next segment."""
    timestamp = int(datetime.datetime.now().timestamp())
    return os.path.join(
        config.temp_segments_folder,
        f"{timestamp}.{config.extension}",
    )


class GstRunner:
    """Run a GStreamer pipeline and push frames onto a queue."""

    def __init__(
        self,
        config: GstProcessConfig,
        frame_queue: Queue[bytes],  # pylint: disable=unsubscriptable-object
        exit_event: Event,
    ) -> None:
        self._config = config
        self._frame_queue = frame_queue
        self._exit_event = exit_event
        self._logger = logging.getLogger(
            f"viseron.components.gstreamer.stream.{config.camera_identifier}"
        )
        self._logger_gstreamer = logging.getLogger(f"{self._logger.name}.gstreamer")

    def on_new_sample(self, app_sink: GstApp.AppSink) -> Gst.FlowReturn:
        """Read a sample from the appsink and queue its bytes."""
        sample = app_sink.emit("pull-sample")
        if not isinstance(sample, Gst.Sample):
            self._logger.debug("Could not get sample from appsink")
            return Gst.FlowReturn.ERROR

        buffer = sample.get_buffer()
        if not buffer:
            self._logger.debug("Could not get buffer from sample")
            return Gst.FlowReturn.ERROR

        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            self._logger.debug("Could not map buffer data")
            return Gst.FlowReturn.ERROR

        pop_if_full(self._frame_queue, bytes(map_info.data))

        buffer.unmap(map_info)
        return Gst.FlowReturn.OK

    def on_format_location(self, _splitmux, _fragment_id, _udata) -> str:
        """Return the location of the next segment."""
        return segment_location(self._config)

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
    ) -> None:
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

    def run(self) -> None:
        """Run the GStreamer pipeline until the exit event is set."""
        mainloop = GLib.MainLoop()

        Gst.init(None)
        # Remove logging to stderr
        Gst.debug_remove_log_function(None)
        Gst.debug_set_default_threshold(
            CONFIG_LOGLEVEL_TO_GSTREAMER[self._config.gst_loglevel]
        )
        Gst.debug_add_log_function(self.on_gst_log_message, None)

        gst_pipeline = Gst.parse_launch(self._config.pipeline)
        appsink = gst_pipeline.get_by_name(  # type: ignore[attr-defined]
            "sink",
        )
        appsink.connect("new-sample", self.on_new_sample)
        mux = gst_pipeline.get_by_name("mux")  # type: ignore[attr-defined]
        mux.connect("format-location", self.on_format_location, None)

        gst_pipeline.set_state(Gst.State.PLAYING)
        while not self._exit_event.is_set():
            time.sleep(1)

        gst_pipeline.set_state(Gst.State.NULL)
        mainloop.quit()


def run_gstreamer(
    config: GstProcessConfig,
    frame_queue: Queue[bytes],  # pylint: disable=unsubscriptable-object
    exit_event: Event,
) -> None:
    """Entrypoint of the GStreamer child process."""
    setproctitle.setproctitle(config.alias)
    enable_child_logging(config.sensitive_strings, config.log_level)
    GstRunner(config, frame_queue, exit_event).run()
