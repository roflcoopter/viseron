import datetime
import logging
import os
import subprocess as sp
from queue import Empty

import cv2

from lib.cleanup import SegmentCleanup
from lib.segments import Segments

LOGGER = logging.getLogger(__name__)


class FFMPEGRecorder:
    def __init__(self, config, frame_buffer):
        self._logger = logging.getLogger(__name__ + "." + config.camera.name_slug)
        if getattr(config.recorder.logging, "level", None):
            self._logger.setLevel(config.recorder.logging.level)
        elif getattr(config.camera.logging, "level", None):
            self._logger.setLevel(config.camera.logging.level)
        self._logger.debug("Initializing ffmpeg recorder")
        self.config = config
        self.is_recording = False
        self.writer_pipe = None
        self.frame_buffer = frame_buffer
        self._logger.debug(
            "FFMPEG encoder command: "
            f"{' '.join(self.build_command('<file>', '<width>', '<height>', '<fps>'))}"
        )

        segments_folder = os.path.join(
            config.recorder.segments_folder, config.camera.name
        )
        self.create_directory(segments_folder)
        self._segmenter = Segments(self._logger, segments_folder)
        self._segment_cleanup = SegmentCleanup(config)

    def build_command(self, file_name, width, height, fps):
        return (
            ["ffmpeg"]
            + self.config.recorder.global_args
            + ["-loglevel", "error"]
            + self.config.recorder.hwaccel_args
            + [
                "-f",
                "rawvideo",
                "-pix_fmt",
                "nv12",
                "-s:v",
                f"{width}x{height}",
                "-r",
                str(fps),
                "-i",
                "pipe:0",
                "-y",
            ]
            + self.config.recorder.codec
            + self.config.recorder.filter_args
            + [file_name]
        )

    def write_frames(self, file_name, width, height, fps):
        command = self.build_command(file_name, width, height, fps)
        self._logger.debug(f"FFMPEG command: {' '.join(command)}")

        writer_pipe = sp.Popen(
            command, stdin=sp.PIPE, bufsize=int(width * height * 1.5)
        )

        while self.is_recording:
            try:
                frame = self.frame_buffer.get(timeout=5)
                writer_pipe.stdin.write(frame.raw_frame)
            except Empty:
                self._logger.error("Timed out")

        writer_pipe.stdin.close()
        writer_pipe.wait()
        self._logger.info("FFMPEG recorder stopped")

    def subfolder_name(self, today):
        return (
            f"{today.year:04}-{today.month:02}-{today.day:02}/{self.config.camera.name}"
        )

    def create_thumbnail(self, file_name, frame):
        cv2.imwrite(file_name, frame)

    def create_directory(self, path):
        try:
            if not os.path.isdir(path):
                self._logger.info(f"Creating folder {path}")
                os.makedirs(path)
        except FileExistsError:
            self._logger.error(f"{path} already exists")

    def start_recording(self, frame, width, height, fps):
        self._logger.info("Starting recorder")
        self._segment_cleanup.pause()
        self._event_start = int(datetime.datetime.now().timestamp())
        self.is_recording = True

        if self.config.recorder.folder is None:
            self._logger.error("Output directory is not specified")
            return

        # Create filename
        now = datetime.datetime.now()
        video_name = f"{now.strftime('%H:%M:%S')}.{self.config.recorder.extension}"
        thumbnail_name = f"{now.strftime('%H:%M:%S')}.jpg"

        # Create foldername
        subfolder = self.subfolder_name(now)
        full_path = os.path.join(self.config.recorder.folder, subfolder)
        self.create_directory(full_path)

        self.create_thumbnail(
            os.path.join(full_path, thumbnail_name), frame.decoded_frame_umat_rgb
        )
        self._recording_name = os.path.join(full_path, video_name)
        self._recording_name2 = os.path.join(full_path, f"seg-{video_name}")
        self.write_frames(self._recording_name, width, height, fps)

    def stop(self):
        self._logger.info("Stopping recorder")
        self.is_recording = False
        self._segmenter.concat_segments(
            self._event_start - self.config.recorder.lookback,
            int(datetime.datetime.now().timestamp()),
            self._recording_name2,
        )
        self._segment_cleanup.resume()
