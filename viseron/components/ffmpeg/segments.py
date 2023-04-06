"""Concatenate FFmpeg segments to a single video file."""
from __future__ import annotations

import datetime
import os
import shutil
import subprocess as sp
import time
from typing import TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler

from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera import CONFIG_LOOKBACK
from viseron.domains.camera.const import EVENT_RECORDER_COMPLETE
from viseron.domains.camera.recorder import EventRecorderData
from viseron.helpers.logs import LogPipe

from .const import (
    CAMERA_SEGMENT_DURATION,
    CONFIG_FFMPEG_LOGLEVEL,
    CONFIG_RECORDER,
    CONFIG_RECORDER_AUDIO_CODEC,
    CONFIG_RECORDER_AUDIO_FILTERS,
    CONFIG_RECORDER_CODEC,
    CONFIG_RECORDER_HWACCEL_ARGS,
    CONFIG_RECORDER_OUPTUT_ARGS,
    CONFIG_RECORDER_VIDEO_FILTERS,
    CONFIG_SEGMENTS_FOLDER,
    FFMPEG_LOGLEVELS,
)

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains.camera import AbstractCamera
    from viseron.domains.camera.recorder import Recording


class Segments:
    """Concatenate segments between two timestamps on-demand."""

    def __init__(
        self,
        logger,
        config,
        vis: Viseron,
        camera: AbstractCamera,
        segments_folder,
    ) -> None:
        self._logger = logger
        self._config = config
        self._vis = vis
        self._camera = camera
        self._segments_folder = segments_folder

        self._log_pipe = LogPipe(
            self._logger,
            FFMPEG_LOGLEVELS[config[CONFIG_RECORDER][CONFIG_FFMPEG_LOGLEVEL]],
        )

    def segment_duration(self, segment_file):
        """Return the duration of a specified segment."""
        ffprobe_cmd = [
            "ffprobe",
            "-hide_banner",
            "-loglevel",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            f"{segment_file}",
        ]

        tries = 0
        while True:
            with sp.Popen(
                ffprobe_cmd,
                stdout=sp.PIPE,
                stderr=sp.PIPE,
            ) as pipe:
                (output, stderr) = pipe.communicate()
                p_status = pipe.wait()

            if p_status == 0:
                try:
                    return float(output.decode("utf-8").strip())
                except ValueError:
                    pass

            if (
                "moov atom not found" in stderr.decode()
                or output.decode("utf-8").strip() == "N/A"
            ) and tries <= CAMERA_SEGMENT_DURATION + 5:
                self._logger.debug(
                    f"{segment_file} is locked. Trying again in 1 second"
                )
                tries += 1
                time.sleep(1)
                continue
            break

        self._logger.error(
            f"Could not get duration for: {segment_file}. Error: {stderr.decode()}"
        )
        return None

    @staticmethod
    def find_segment(segments, timestamp):
        """Find a segment which includes the given timestamp."""
        return next(
            (
                key
                for key, value in segments.items()
                if value["start_time"] <= timestamp <= value["end_time"]
            ),
            None,
        )

    def get_start_time(self, segment):
        """Get start time of segment."""
        return datetime.datetime.strptime(
            segment.split(".")[0], "%Y%m%d%H%M%S"
        ).timestamp()

    def get_segment_information(self):
        """Get information for all available segments."""
        segment_files = os.listdir(self._segments_folder)
        segment_information: dict[str, dict[str, float]] = {}
        for segment in segment_files:
            duration = self.segment_duration(
                os.path.join(self._segments_folder, segment)
            )
            if not duration:
                continue

            start_time = self.get_start_time(segment)

            information = {"start_time": start_time, "end_time": start_time + duration}
            segment_information[segment] = information
        self._logger.debug(f"Segment information: {segment_information}")
        return segment_information

    def get_concat_segments(
        self,
        segments: dict[str, dict[str, float]],
        start_segment: str,
        end_segment: str,
    ) -> list[str] | None:
        """Return all segments between start_segment and end_segment."""
        # Sort segments by start time
        segment_list = sorted(
            segments.keys(), key=lambda x: (segments[x]["start_time"])
        )
        try:
            return segment_list[
                len(segment_list)
                - segment_list[::-1].index(start_segment)
                - 1 : segment_list.index(end_segment)
                + 1
            ]
        except ValueError:
            pass

        self._logger.error("Matching segments could not be found")
        return None

    def generate_segment_script(
        self,
        segments_to_concat: list[str],
        segment_information: dict[str, dict[str, float]],
        event_start: float,
        event_end: float,
    ) -> str:
        """Return a script string with information of each segment to concatenate."""
        segment_iterable = iter(segments_to_concat)
        segment = next(segment_iterable)
        concat_script = []
        concat_script.append(
            f"file 'file:{os.path.join(self._segments_folder, segment)}'"
        )

        inpoint = max(int(event_start - segment_information[segment]["start_time"]), 0)
        if inpoint:
            concat_script.append(f"inpoint {inpoint}")

        try:
            segment = next(segment_iterable)
            while True:
                concat_script.append(
                    f"file 'file:{os.path.join(self._segments_folder, segment)}'"
                )
                segment = next(segment_iterable)
        except StopIteration:
            outpoint = int(event_end - segment_information[segment]["start_time"])
            # If outpoint is larger than segment duration, dont add it to the script
            if (
                outpoint + segment_information[segment]["start_time"]
                < segment_information[segment]["end_time"]
            ):
                concat_script.append(f"outpoint {outpoint}")
            return "\n".join(concat_script)

    def video_filter_args(self):
        """Return video filter arguments."""
        if filters := self._config[CONFIG_RECORDER][CONFIG_RECORDER_VIDEO_FILTERS]:
            return [
                "-vf",
                ",".join(filters),
            ]
        return []

    def audio_filter_args(self):
        """Return audio filter arguments."""
        if filters := self._config[CONFIG_RECORDER][CONFIG_RECORDER_AUDIO_FILTERS]:
            return [
                "-af",
                ",".join(filters),
            ]
        return []

    def ffmpeg_concat(self, segment_script, file_name) -> None:
        """Generate and run FFmpeg command to concatenate segments."""
        ffmpeg_cmd = (
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                self._config[CONFIG_RECORDER][CONFIG_FFMPEG_LOGLEVEL],
                "-y",
            ]
            + self._config[CONFIG_RECORDER][CONFIG_RECORDER_HWACCEL_ARGS]
            + [
                "-protocol_whitelist",
                "file,pipe",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                "-",
            ]
            + ["-c:v", self._config[CONFIG_RECORDER][CONFIG_RECORDER_CODEC]]
            + self.video_filter_args()
            + ["-c:a", self._config[CONFIG_RECORDER][CONFIG_RECORDER_AUDIO_CODEC]]
            + self.audio_filter_args()
            + self._config[CONFIG_RECORDER][CONFIG_RECORDER_OUPTUT_ARGS]
            + ["-movflags", "+faststart"]
            + [file_name]
        )

        self._logger.debug(f"Concatenation command: {' '.join(ffmpeg_cmd)}")
        self._logger.debug(f"Segment script: \n{segment_script}")

        sp.run(  # type: ignore[call-overload]
            ffmpeg_cmd,
            input=segment_script,
            text=True,
            check=True,
            stderr=self._log_pipe,
        )

    def concat_segments(self, recording: Recording) -> None:
        """Concatenate segments between event_start and event_end."""
        event_start: float = (
            recording.start_timestamp - self._config[CONFIG_RECORDER][CONFIG_LOOKBACK]
        )
        event_end = (
            recording.end_timestamp
            if recording.end_timestamp
            else datetime.datetime.now().timestamp()
        )
        self._logger.debug("Concatenating segments")
        segment_information = self.get_segment_information()
        if not segment_information:
            self._logger.error("No segments were found")
            return

        start_segment = self.find_segment(segment_information, event_start)
        if not start_segment:
            self._logger.warning(
                "Could not find matching start segment. Using earliest possible"
            )
            start_segment = min(segment_information.keys())

        end_segment = self.find_segment(segment_information, event_end)
        if not end_segment:
            self._logger.warning(
                "Could not find matching end segment. Using latest possible"
            )
            end_segment = max(segment_information.keys())

        self._logger.debug(f"Start event: {event_start}, segment: {start_segment}")
        self._logger.debug(f"End event: {event_end}, segment: {end_segment}")
        segments_to_concat = self.get_concat_segments(
            segment_information, start_segment, end_segment
        )

        if not segments_to_concat:
            return

        temp_file = os.path.join("/tmp", recording.path)

        try:
            self.ffmpeg_concat(
                self.generate_segment_script(
                    segments_to_concat, segment_information, event_start, event_end
                ),
                temp_file,
            )
            shutil.move(temp_file, recording.path)
        except sp.CalledProcessError as error:
            self._logger.error("Failed to concatenate segments: %s", error)
            return

        self._vis.dispatch_event(
            EVENT_RECORDER_COMPLETE,
            EventRecorderData(
                camera=self._camera,
                recording=recording,
            ),
        )

        for segment in segments_to_concat[:-1]:
            self._logger.debug(f"Removing segment: {segment}")
            os.remove(os.path.join(self._segments_folder, segment))

        self._logger.debug("Segments concatenated")


class SegmentCleanup:
    """Clean up segments created by FFmpeg."""

    def __init__(
        self, vis, config, camera_name, logger, segment_thread_context
    ) -> None:
        self._vis = vis
        self._logger = logger
        self._segment_thread_context = segment_thread_context
        self._directory = os.path.join(config[CONFIG_SEGMENTS_FOLDER], camera_name)
        # Make sure we dont delete a segment which is needed by recorder
        self._max_age = config[CONFIG_LOOKBACK] + (CAMERA_SEGMENT_DURATION * 3)
        self._scheduler = BackgroundScheduler(timezone="UTC", daemon=True)
        self._scheduler.add_job(
            self.cleanup,
            "interval",
            seconds=CAMERA_SEGMENT_DURATION,
            id="segment_cleanup",
        )
        self._scheduler.start()

        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self.shutdown)

    def get_start_time(self, segment):
        """Get start time of segment."""
        return datetime.datetime.strptime(
            segment.split(".")[0], "%Y%m%d%H%M%S"
        ).timestamp()

    def cleanup(self, force=False) -> None:
        """Delete all segments that are no longer needed."""
        if not force and self._segment_thread_context.count > 0:
            self._logger.debug(
                "Skipping segment cleanup since segment concatenation is running"
            )
            return

        now = datetime.datetime.now().timestamp()
        for segment in os.listdir(self._directory):
            if force:
                os.remove(os.path.join(self._directory, segment))
                continue

            try:
                start_time = self.get_start_time(segment)
            except ValueError as error:
                self._logger.error(
                    f"Could not extract timestamp from segment {segment}: {error}"
                )
                continue

            if now - start_time > self._max_age:
                os.remove(os.path.join(self._directory, segment))

    def start(self) -> None:
        """Start the scheduler."""
        self._logger.debug("Starting segment cleanup")
        self._scheduler.start()

    def pause(self) -> None:
        """Pauise the scheduler."""
        self._logger.debug("Pausing segment cleanup")
        self._scheduler.pause_job("segment_cleanup")

    def resume(self) -> None:
        """Resume the scheduler."""
        self._logger.debug("Resuming segment cleanup")
        self._scheduler.resume_job("segment_cleanup")

    def shutdown(self) -> None:
        """Resume the scheduler."""
        self._logger.debug("Shutting down segment cleanup")
        self.cleanup(force=True)
        self._scheduler.shutdown()
