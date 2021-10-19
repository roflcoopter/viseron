"""Concatenate FFmpeg segments to a single video file."""
import datetime
import os
import shutil
import subprocess as sp
import time

from apscheduler.schedulers.background import BackgroundScheduler

from viseron.domains.camera import CONFIG_LOOKBACK

from .const import (
    CAMERA_SEGMENT_DURATION,
    CONFIG_AUDIO_CODEC,
    CONFIG_CODEC,
    CONFIG_FILTER_ARGS,
    CONFIG_HWACCEL_ARGS,
    CONFIG_SEGMENTS_FOLDER,
)


class Segments:
    """Concatenate segments between two timestamps on-demand."""

    def __init__(
        self,
        logger,
        config,
        segments_folder,
    ):
        self._logger = logger
        self._config = config
        self._segments_folder = segments_folder

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
            with sp.Popen(ffprobe_cmd, stdout=sp.PIPE, stderr=sp.PIPE) as pipe:
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

    def get_segment_information(self):
        """Get information for all available segments."""
        segment_files = os.listdir(self._segments_folder)
        segment_information: dict = {}
        for segment in segment_files:
            duration = self.segment_duration(
                os.path.join(self._segments_folder, segment)
            )
            if not duration:
                continue

            start_time = datetime.datetime.strptime(
                segment.split(".")[0], "%Y%m%d%H%M%S"
            ).timestamp()

            information = {"start_time": start_time, "end_time": start_time + duration}
            segment_information[segment] = information
        self._logger.debug(f"Segment information: {segment_information}")
        return segment_information

    def get_concat_segments(self, segments, start_segment, end_segment):
        """Return all segments between start_segment and end_segment."""
        segment_list = list(segments.keys())
        segment_list.sort()
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
        self, segments_to_concat, segment_information, event_start, event_end
    ):
        """Return a script string with information of each segment to concatenate."""
        segment_iterable = iter(segments_to_concat)
        segment = next(segment_iterable)
        concat_script = f"file 'file:{os.path.join(self._segments_folder, segment)}'"
        concat_script += (
            f"\ninpoint {int(event_start-segment_information[segment]['start_time'])}"
        )

        try:
            segment = next(segment_iterable)
        except StopIteration:
            concat_script += (
                "\noutpoint "
                f"{int(event_end-segment_information[segment]['start_time'])}"
            )
            return concat_script

        while True:
            try:
                concat_script += (
                    "\nfile " f"'file:{os.path.join(self._segments_folder, segment)}'"
                )
                segment = next(segment_iterable)
            except StopIteration:
                concat_script += (
                    "\noutpoint "
                    f"{int(event_end-segment_information[segment]['start_time'])}"
                )
                return concat_script

    def ffmpeg_concat(self, segment_script, file_name):
        """Generate and run FFmpeg command to concatenate segments."""
        ffmpeg_cmd = (
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
            ]
            + self._config[CONFIG_HWACCEL_ARGS]
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
            + self._config[CONFIG_CODEC]
            + self._config[CONFIG_AUDIO_CODEC]
            + self._config[CONFIG_FILTER_ARGS]
            + ["-movflags", "+faststart"]
            + [file_name]
        )

        self._logger.debug(f"Concatenation command: {ffmpeg_cmd}")
        self._logger.debug(f"Segment script: \n{segment_script}")

        pipe = sp.run(ffmpeg_cmd, input=segment_script, encoding="ascii", check=True)
        if pipe.returncode != 0:
            self._logger.error(f"Error concatenating segments: {pipe.stderr}")

    def concat_segments(self, event_start, event_end, file_name):
        """Concatenate segments between event_start and event_end."""
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

        temp_file = os.path.join("/tmp", file_name)

        try:
            self.ffmpeg_concat(
                self.generate_segment_script(
                    segments_to_concat, segment_information, event_start, event_end
                ),
                temp_file,
            )
            shutil.move(temp_file, file_name)
        except sp.CalledProcessError as error:
            self._logger.error("Failed to concatenate segments: %s", error)
            return

        self._logger.debug("Segments concatenated")


class SegmentCleanup:
    """Clean up segments created by FFmpeg."""

    def __init__(self, config, camera_name, logger):
        self._logger = logger
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

    def cleanup(self):
        """Delete all segments that are no longer needed."""
        now = datetime.datetime.now().timestamp()
        for segment in os.listdir(self._directory):
            try:
                start_time = datetime.datetime.strptime(
                    segment.split(".")[0], "%Y%m%d%H%M%S"
                ).timestamp()
            except ValueError as error:
                self._logger.error(
                    f"Could not extract timestamp from segment {segment}: {error}"
                )
                continue

            if now - start_time > self._max_age:
                os.remove(os.path.join(self._directory, segment))

    def start(self):
        """Start the scheduler."""
        self._logger.debug("Starting segment cleanup")
        self._scheduler.start()

    def pause(self):
        """Pauise the scheduler."""
        self._logger.debug("Pausing segment cleanup")
        self._scheduler.pause_job("segment_cleanup")

    def resume(self):
        """Resume the scheduler."""
        self._logger.debug("Resuming segment cleanup")
        self._scheduler.resume_job("segment_cleanup")
