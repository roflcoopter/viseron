import datetime
import os
import subprocess as sp
import time

from const import CAMERA_SEGMENT_DURATION


class Segments:
    def __init__(self, logger, segment_folder):
        self._logger = logger
        self._segment_folder = segment_folder

    def segment_duration(self, segment_file):
        """Returns the duration of a specified segment"""
        ffprobe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            f"{segment_file}",
        ]

        tries = 0
        while True:
            pipe = sp.Popen(ffprobe_cmd, stdout=sp.PIPE, stderr=sp.PIPE)
            (output, stderr) = pipe.communicate()
            p_status = pipe.wait()

            if p_status == 0:
                return float(output.decode("utf-8").strip())

            if (
                "moov atom not found" in stderr.decode()
                and tries <= CAMERA_SEGMENT_DURATION + 1
            ):
                self._logger.debug(
                    f"{segment_file} is locked. Trying again in 1 second."
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
        """Finds a segment which includes the given timestamp"""
        return next(
            (
                key
                for key, value in segments.items()
                if value["start_time"] <= timestamp <= value["end_time"]
            ),
            None,
        )

    def get_segment_information(self):
        """Gets information for all available segments"""
        segment_files = os.listdir(self._segment_folder)
        self._logger.debug(f"Files in {self._segment_folder}: {segment_files}")
        segment_information: dict = {}
        for segment in segment_files:
            duration = self.segment_duration(
                os.path.join(self._segment_folder, segment)
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
        """Returns all segments between start_segment and end_segment"""
        segment_list = list(segments.keys())
        segment_list.sort()
        self._logger.debug(f"Sorted segments: {segment_list}")
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
        """Returns a script string with information of each segment to concatenate"""
        segment_iterable = iter(segments_to_concat)
        segment = next(segment_iterable)
        concat_script = f"file '{os.path.join(self._segment_folder, segment)}'"
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
                    f"\nfile '{os.path.join(self._segment_folder, segment)}'"
                )
                segment = next(segment_iterable)
            except StopIteration:
                concat_script += (
                    "\noutpoint "
                    f"{int(event_end-segment_information[segment]['start_time'])}"
                )
                return concat_script

    def ffmpeg_concat(self, segment_script, file_name):
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-protocol_whitelist",
            "pipe,file",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            "-",
            "-c",
            "copy",
            file_name,
        ]

        self._logger.debug(f"Concatenation command: {ffmpeg_cmd}")
        self._logger.debug(f"Segment script: {segment_script}")

        pipe = sp.run(ffmpeg_cmd, input=segment_script, encoding="ascii", check=True)

        if pipe.returncode != 0:
            self._logger.error(f"Error concatenating segments: {pipe.stderr}")

    def concat_segments(self, event_start, event_end, file_name):
        """Concatenates segments between event_start and event_end"""
        self._logger.debug("Concatenating segments")
        segment_information = self.get_segment_information()
        if not segment_information:
            self._logger.error("No segments were found")
            return

        start_segment = self.find_segment(segment_information, event_start)
        end_segment = self.find_segment(segment_information, event_end)
        self._logger.debug(f"Start segment: {start_segment}")
        self._logger.debug(f"End segment: {end_segment}")
        segments_to_concat = self.get_concat_segments(
            segment_information, start_segment, end_segment
        )

        self._logger.debug(f"Segments to concatenate: {segments_to_concat}")
        if not segments_to_concat:
            return

        self.ffmpeg_concat(
            self.generate_segment_script(
                segments_to_concat, segment_information, event_start, event_end
            ),
            file_name,
        )
        self._logger.debug("Segments concatenated")