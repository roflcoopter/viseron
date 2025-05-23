"""Convert MP4 to fragmented MP4 for streaming."""
from __future__ import annotations

import datetime
import logging
import multiprocessing as mp
import os
import queue
import re
import shutil
import subprocess as sp
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from math import ceil
from typing import TYPE_CHECKING, Literal, TypedDict

import psutil
from path import Path

from viseron.components.storage.const import COMPONENT as STORAGE_COMPONENT
from viseron.components.storage.models import FilesMeta
from viseron.components.storage.queries import get_time_period_fragments
from viseron.const import CAMERA_SEGMENT_DURATION, TEMP_DIR, VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera.const import CONFIG_FFMPEG_LOGLEVEL, CONFIG_RECORDER
from viseron.helpers import get_utc_offset
from viseron.helpers.child_process_worker import ChildProcessWorker
from viseron.helpers.logs import LogPipe

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from viseron import Viseron
    from viseron.components.storage import Storage
    from viseron.domains.camera import AbstractCamera


def _get_open_files(path: str, process: psutil.Process) -> list[str]:
    """Get open files for a process."""
    files = []
    try:
        open_files = process.open_files()
        for file in open_files:
            if file.path.startswith(f"{path}/"):
                files.append(file.path.split("/")[-1])
    except psutil.Error:
        pass
    return files


def _get_mp4_files_to_fragment(path: str) -> list[str]:
    """Get mp4 files that are not in use by ffmpeg/gstreamer."""
    mp4_files = [
        file for file in Path(path).walkfiles() if file.endswith((".mp4", ".m4s"))
    ]
    files_in_use = ["init.mp4"]
    for process in psutil.process_iter():
        try:
            process_name = process.name()
            if any(pattern in process_name for pattern in ["ffmpeg", "gstreamer"]):
                files_in_use.extend(_get_open_files(path, process))
        except psutil.Error:
            pass
    return [str(f.name) for f in mp4_files if str(f.name) not in files_in_use]


def _extract_extinf_number(playlist_content: str, file: str) -> float | None:
    """Extract the EXTINF number from a HLS playlist."""
    # Escape special regex characters in the file name
    escaped_file = re.escape(file)

    # Simplified pattern
    pattern = rf"#EXTINF:(\d+(?:\.\d+)?)[^\n]*\n(?:(?!#EXTINF)[^\n]*\n)*{escaped_file}"

    match = re.search(pattern, playlist_content)

    if match:
        # Extract the duration number from the match
        return float(match.group(1))
    return None


def _extract_program_date_time(
    playlist_content: str, file: str
) -> datetime.datetime | None:
    """Extract the EXT-X-PROGRAM-DATE-TIME number from a HLS playlist."""
    escaped_file = re.escape(file)
    pattern = (
        r"#EXT-X-PROGRAM-DATE-TIME:"
        rf"([^\n]+)\n(?:(?!#EXT-X-PROGRAM-DATE-TIME)[^\n]*\n)*{escaped_file}"
    )

    match = re.search(pattern, playlist_content)

    try:
        if match:
            # Remove timezone information since fromisoformat does not support it
            no_tz = re.sub(r"\+[0-9]{4}$", "", match.group(1))
            # Adjust according to local timezone
            return (datetime.datetime.fromisoformat(no_tz) - get_utc_offset()).replace(
                tzinfo=datetime.timezone.utc
            )
    except ValueError:
        pass
    return None


class FragmenterSubProcessWorker(ChildProcessWorker):
    """Child process worker for running fragmentation in a child process."""

    def __init__(
        self,
        vis: Viseron,
        camera: AbstractCamera,
        temp_segments_folder: str,
        segments_folder: str,
        metadata_callback: Callable[[dict], None] | None,
    ):
        self._logger = logging.getLogger(
            f"{self.__module__}.subprocess.{camera.identifier}"
        )
        self.temp_segments_folder = temp_segments_folder
        self.segments_folder = segments_folder
        self._log_pipe = LogPipe(
            logging.getLogger(f"{self.__module__}.{camera.identifier}.mp4box"),
            logging.DEBUG,
        )

        self._worker_event = mp.Event()
        self.on_metadata = metadata_callback
        super().__init__(
            vis,
            f"fragmenter.{camera.identifier}",
        )

    def work_input(self, item):
        """Handle input commands in the child process."""
        if item.get("cmd") == "fragment":
            self._logger.debug(
                "Checking for new segments to fragment in "
                f"{self.temp_segments_folder}"
            )
            mp4s = _get_mp4_files_to_fragment(self.temp_segments_folder)
            for mp4 in sorted(mp4s)[:5]:
                self._logger.debug(f"Processing {mp4}")
                if mp4.split(".")[1] == "m4s":
                    self._handle_m4s(mp4)
                else:
                    self._handle_mp4(mp4)

    def work_output(self, item):
        """Relay metadata from child process to main process via callback."""
        if item is not None and self.on_metadata:
            self.on_metadata(item)
            self._worker_event.set()

    def _mp4box_command(self, file: str):
        """Create fragmented fmp4 from mp4 using MP4Box."""
        outdir = os.path.join(self.temp_segments_folder, file.split(".")[0])
        os.makedirs(outdir, exist_ok=True)
        try:
            sp.run(  # type: ignore[call-overload]
                [
                    "MP4Box",
                    "-logs",
                    "dash@error:ncl",
                    "-noprog",
                    "-dash",
                    "10000",
                    "-rap",
                    "-frag-rap",
                    "-segment-name",
                    "clip_",
                    "-out",
                    os.path.join(outdir, "master.m3u8"),
                    os.path.join(self.temp_segments_folder, file),
                ],
                stdout=self._log_pipe,
                stderr=self._log_pipe,
                check=True,
            )
        except sp.CalledProcessError as err:
            self._logger.error("MP4Box command failed", exc_info=err)
            return False
        return True

    def _move_to_segments_folder_mp4box(self, file: str):
        """Move fragmented mp4 created by mp4box to segments folder."""
        try:
            shutil.move(
                os.path.join(
                    self.temp_segments_folder,
                    file.split(".")[0],
                    "clip_1.m4s",
                ),
                os.path.join(self.segments_folder, file.split(".")[0] + ".m4s"),
            )
            shutil.move(
                os.path.join(
                    self.temp_segments_folder,
                    file.split(".")[0],
                    "clip_init.mp4",
                ),
                os.path.join(self.segments_folder, "init.mp4"),
            )
        except FileNotFoundError:
            self._logger.debug(f"{file} not found")

    def _move_to_segments_folder(self, file: str):
        """Move fragmented mp4 created by encoder to segments folder."""
        try:
            shutil.move(
                os.path.join(self.temp_segments_folder, file),
                os.path.join(self.segments_folder, file),
            )
            shutil.copy(
                os.path.join(self.temp_segments_folder, "init.mp4"),
                os.path.join(self.segments_folder, "init.mp4"),
            )
        except FileNotFoundError:
            self._logger.debug(f"{file} not found", exc_info=True)

    def _write_files_metadata(
        self,
        file: str,
        extinf: float,
        program_date_time: datetime.datetime | None = None,
    ):
        """Save temporary metadata which is later used when inserting into the DB."""
        if program_date_time:
            orig_ctime = program_date_time
        else:
            orig_ctime = (
                datetime.datetime.fromtimestamp(int(file.split(".")[0]), tz=None)
                - get_utc_offset()
            )
            orig_ctime = orig_ctime.replace(tzinfo=datetime.timezone.utc)

        path = os.path.join(self.segments_folder, file.split(".")[0] + ".m4s")

        self._worker_event.clear()
        self._output_queue.put(
            {
                "path": path,
                "orig_ctime": orig_ctime,
                "duration": extinf,
            }
        )
        self._worker_event.wait(timeout=1)

    def _read_m3u8_mp4box(self, file: str) -> str:
        """Read m3u8 file created by MP4Box."""
        return open(
            os.path.join(
                self.temp_segments_folder,
                file.split(".")[0],
                "master_1.m3u8",
            ),
            encoding="utf-8",
        ).read()

    def _read_m3u8(self) -> str:
        """Read m3u8 file created by encoder."""
        return open(
            os.path.join(
                self.temp_segments_folder,
                "index.m3u8",
            ),
            encoding="utf-8",
        ).read()

    def _handle_mp4(self, file: str):
        """Handle mp4 files."""
        try:
            if self._mp4box_command(file):
                extinf = _extract_extinf_number(
                    self._read_m3u8_mp4box(file), "clip_1.m4s"
                )
                if extinf:
                    self._write_files_metadata(file, extinf)
                    self._move_to_segments_folder_mp4box(file)
                else:
                    self._logger.error(f"Failed to get extinf for {file}")
        except Exception as err:  # pylint: disable=broad-except
            self._logger.error(f"Failed to fragment {file}", exc_info=err)

        try:
            os.remove(os.path.join(self.temp_segments_folder, file))
            shutil.rmtree(
                os.path.join(self.temp_segments_folder, file.split(".")[0]),
            )
        except FileNotFoundError as err:
            self._logger.error("Failed to delete broken fragment", exc_info=err)

    def _handle_m4s(self, file: str):
        """Handle m4s (fragmented mp4) files."""
        try:
            m3u8 = self._read_m3u8()
            extinf = _extract_extinf_number(m3u8, file)
            program_date_time = _extract_program_date_time(m3u8, file)
            if extinf:
                self._write_files_metadata(file, extinf, program_date_time)
                self._move_to_segments_folder(file)
            else:
                self._logger.error(f"Failed to get extinf for {file}")
                os.remove(os.path.join(self.temp_segments_folder, file))
        except Exception as err:  # pylint: disable=broad-except
            self._logger.error(f"Failed to process m4s file {file}", exc_info=err)
        finally:
            try:
                os.remove(os.path.join(self.temp_segments_folder, file))
            except FileNotFoundError:
                pass

    def stop(self) -> None:
        """Stop the child process."""
        super().stop()
        self._log_pipe.close()


class Fragmenter:
    """Convert MP4 to fragmented MP4 for streaming."""

    def __init__(
        self,
        vis: Viseron,
        camera: AbstractCamera,
    ) -> None:
        self._logger = logging.getLogger(f"{self.__module__}.{camera.identifier}")
        self._vis = vis
        self._camera = camera
        self._storage: Storage = vis.data[STORAGE_COMPONENT]
        os.makedirs(camera.temp_segments_folder, exist_ok=True)
        self._storage.ignore_file("init.mp4")

        self._log_pipe_ffmpeg = LogPipe(
            logging.getLogger(f"{self.__module__}.{camera.identifier}.ffmpeg"),
            logging.ERROR,
        )

        # Subprocess worker for fragmentation
        self._fragment_worker = FragmenterSubProcessWorker(
            vis,
            camera,
            camera.temp_segments_folder,
            camera.segments_folder,
            self._on_metadata_from_worker,
        )

        self._fragment_job_id = f"fragment_{self._camera.identifier}"
        self._vis.background_scheduler.add_job(
            self._fragment_command,
            "interval",
            seconds=1,
            id=self._fragment_job_id,
            max_instances=1,
            coalesce=True,
        )
        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self._shutdown)

    def _on_metadata_from_worker(self, item):
        """Update temporary_files_meta with metadata from subprocess."""
        self._storage.temporary_files_meta[item["path"]] = FilesMeta(
            orig_ctime=item["orig_ctime"], duration=item["duration"]
        )

    def _fragment_command(self):
        """Periodically send work to the subprocess."""
        try:
            self._fragment_worker.input_queue.put({"cmd": "fragment"}, timeout=1)
        except queue.Full:
            pass

    def _shutdown(self) -> None:
        """Handle shutdown event."""
        self._logger.debug("Shutting down fragment thread")
        if not self._camera.stopped.is_set():
            self._camera.stopped.wait(timeout=5)
        self._log_pipe_ffmpeg.close()

    def concatenate_fragments(
        self, fragments: list[Fragment], media_sequence=0
    ) -> str | Literal[False]:
        """Concatenate fragments into a single mp4 file."""
        file_uuid = str(uuid.uuid4())
        filename = os.path.join(TEMP_DIR, f"{file_uuid}.mp4")

        playlist = generate_playlist(
            fragments,
            os.path.join(self._camera.segments_folder, "init.mp4"),
            media_sequence=media_sequence,
            end=True,
            file_directive=True,
        )
        self._logger.debug(f"HLS Playlist for concatenation: {playlist}")
        ffmpeg_cmd = (
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                self._camera.config[CONFIG_RECORDER][CONFIG_FFMPEG_LOGLEVEL],
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                "-",
                "-c:v",
                "copy",
                "-c:a",
                "copy",
            ]
            + ["-movflags", "+faststart"]
            + [filename]
        )
        self._logger.debug(f"Concatenation command: {' '.join(ffmpeg_cmd)}")
        try:
            sp.run(  # type: ignore[call-overload]
                ffmpeg_cmd,
                input=playlist.encode("utf-8"),
                stdout=self._log_pipe_ffmpeg,
                stderr=self._log_pipe_ffmpeg,
                check=True,
            )
        except (sp.CalledProcessError, OSError) as err:
            self._logger.error(err)
            return False
        return filename


def _get_file_path(
    file: str,
    file_directive: bool,
) -> str:
    """Prepend 'file:' directive to file path if file_directive is True.

    'file:' Needed when ffmpeg reads a playlist from stdin.
    """
    if file_directive:
        return f"file:{file}"
    return file


def gap_in_fragments(prev_fragment: Fragment, fragment: Fragment) -> bool:
    """Check if there is a gap between two fragments."""
    return (
        fragment.creation_time
        - (
            prev_fragment.creation_time
            + datetime.timedelta(seconds=prev_fragment.duration)
        )
    ).total_seconds() > 1


def generate_playlist(
    fragments: list[Fragment],
    init_file: str,
    media_sequence=0,
    end=False,
    file_directive=False,
) -> str:
    """Generate a playlist from a list of fragments."""
    playlist = []
    playlist.append("#EXTM3U")
    playlist.append("#EXT-X-VERSION:6")

    playlist.append(f"#EXT-X-MEDIA-SEQUENCE:{media_sequence}")
    if media_sequence:
        playlist.append(f"#EXT-X-DISCONTINUITY-SEQUENCE:{media_sequence}")

    if fragments:
        target_duration = ceil(max(f.duration for f in fragments))
        playlist.append(
            f"#EXT-X-TARGETDURATION:{max(target_duration, CAMERA_SEGMENT_DURATION)}"
        )
    else:
        playlist.append(f"#EXT-X-TARGETDURATION:{CAMERA_SEGMENT_DURATION}")

    playlist.append("#EXT-X-INDEPENDENT-SEGMENTS")
    playlist.append(f'#EXT-X-MAP:URI="{_get_file_path(init_file, file_directive)}"')

    prev_fragment: Fragment | None = None
    for fragment in fragments:
        if prev_fragment and gap_in_fragments(prev_fragment, fragment):
            playlist.append("#EXT-X-DISCONTINUITY")
        program_date_time = fragment.creation_time.replace(
            tzinfo=datetime.timezone.utc
        ).isoformat(timespec="milliseconds")
        playlist.append(f"#EXT-X-PROGRAM-DATE-TIME:{program_date_time}")
        playlist.append(f"#EXTINF:{fragment.duration},")
        playlist.append(_get_file_path(fragment.path, file_directive))
        prev_fragment = fragment
    if end:
        playlist.append("#EXT-X-ENDLIST")
    return "\n".join(playlist)


@dataclass
class Fragment:
    """Represents a fragment of a mp4 file."""

    filename: str
    path: str
    duration: float
    creation_time: datetime.datetime


class Timespan(TypedDict):
    """Timespan of available HLS fragments."""

    start: int
    end: int
    duration: int


def get_available_timespans(
    get_session: Callable[[], Session],
    camera_identifiers: list[str],
    time_from: int | float,
    time_to: int | float | None = None,
) -> list[Timespan]:
    """Get the available timespans of HLS fragments for a time period."""
    files = get_time_period_fragments(
        camera_identifiers, time_from, time_to, get_session
    )
    fragments = [
        Fragment(
            file.filename,
            f"/files{file.path}",
            file.duration,
            file.orig_ctime,
        )
        for file in files
    ]

    timespans: list[Timespan] = []
    start = None
    end = None
    for fragment in fragments:
        if start is None:
            start = fragment.creation_time.timestamp()
        if end is None:
            end = fragment.creation_time.timestamp() + fragment.duration
        if fragment.creation_time.timestamp() > end + fragment.duration:
            timespans.append(
                {"start": int(start), "end": int(end), "duration": int(end - start)}
            )
            start = None
            end = None
        else:
            end = fragment.creation_time.timestamp() + fragment.duration
    if start is not None and end is not None:
        timespans.append(
            {"start": int(start), "end": int(end), "duration": int(end - start)}
        )
    return timespans
