"""Convert MP4 to fragmented MP4 for streaming."""
from __future__ import annotations

import datetime
import logging
import os
import re
import shutil
import subprocess as sp
import time
import uuid
from dataclasses import dataclass
from math import ceil
from typing import TYPE_CHECKING, Literal

import psutil
from path import Path
from sqlalchemy import insert

from viseron.components.storage.const import COMPONENT as STORAGE_COMPONENT
from viseron.components.storage.models import FilesMeta
from viseron.const import TEMP_DIR, VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera.const import CONFIG_FFMPEG_LOGLEVEL, CONFIG_RECORDER
from viseron.helpers.logs import LogPipe

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.storage import Storage
    from viseron.domains.camera import AbstractCamera


def _get_open_files(path: str, process: psutil.Process) -> list[str]:
    """Get open files for a process."""
    files = []
    try:
        open_files = process.open_files()
        for file in open_files:
            if file.path.startswith(path):
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
    pattern = (
        r"^(?:.*?\n)*#EXTINF:([0-9.]+),\s*(?:\n\s*.*?)*?\n\s*"
        rf"{re.escape(file)}(?:\s*\n|$)"
    )

    match = re.search(pattern, playlist_content, re.MULTILINE)

    if match:
        # Extract the duration number from the match
        return float(match.group(1))
    return None


def _extract_program_date_time(
    playlist_content: str, file: str
) -> datetime.datetime | None:
    """Extract the EXT-X-PROGRAM-DATE-TIME number from a HLS playlist."""
    pattern = (
        rf"^#EXT-X-PROGRAM-DATE-TIME:(.*)\s*(?:\n\s*)?{re.escape(file)}(?:\s*\n|$)"
    )

    match = re.search(pattern, playlist_content, re.MULTILINE)

    try:
        if match:
            # Remove timezone information since fromisoformat does not support it
            no_tz = re.sub(r"\+[0-9]{4}$", "", match.group(1))
            # Adjust according to local timezone
            return datetime.datetime.fromisoformat(no_tz) - datetime.timedelta(
                seconds=time.localtime().tm_gmtoff
            )
    except ValueError:
        pass
    return None


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

        self._log_pipe = LogPipe(
            logging.getLogger(f"{self.__module__}.{camera.identifier}.mp4box"),
            logging.DEBUG,
        )
        self._log_pipe_ffmpeg = LogPipe(
            logging.getLogger(f"{self.__module__}.{camera.identifier}.ffmpeg"),
            logging.ERROR,
        )
        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self._shutdown)
        self._fragment_job_id = f"fragment_{self._camera.identifier}"
        self._vis.background_scheduler.add_job(
            self._create_fragmented_mp4,
            "interval",
            seconds=1,
            id=self._fragment_job_id,
            max_instances=1,
        )

    def _mp4box_command(self, file: str):
        """Create fragmented fmp4 from mp4 using MP4Box."""
        outdir = os.path.join(self._camera.temp_segments_folder, file.split(".")[0])
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
                    os.path.join(self._camera.temp_segments_folder, file),
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
                    self._camera.temp_segments_folder,
                    file.split(".")[0],
                    "clip_1.m4s",
                ),
                os.path.join(self._camera.segments_folder, file.split(".")[0] + ".m4s"),
            )
            shutil.move(
                os.path.join(
                    self._camera.temp_segments_folder,
                    file.split(".")[0],
                    "clip_init.mp4",
                ),
                os.path.join(self._camera.segments_folder, "init.mp4"),
            )
        except FileNotFoundError:
            self._logger.debug(f"{file} not found")

    def _move_to_segments_folder(self, file: str):
        """Move fragmented mp4 created by encoder to segments folder."""
        try:
            shutil.move(
                os.path.join(self._camera.temp_segments_folder, file),
                os.path.join(self._camera.segments_folder, file),
            )
            shutil.copy(
                os.path.join(self._camera.temp_segments_folder, "init.mp4"),
                os.path.join(self._camera.segments_folder, "init.mp4"),
            )
        except FileNotFoundError:
            self._logger.debug(f"{file} not found", exc_info=True)

    def _write_files_metadata(
        self,
        file: str,
        extinf: float,
        program_date_time: datetime.datetime | None = None,
    ):
        """Write metadata about the fragmented mp4 to the database."""
        with self._storage.get_session() as session:
            if program_date_time:
                orig_ctime = program_date_time
            else:
                orig_ctime = datetime.datetime.fromtimestamp(
                    int(file.split(".")[0]), tz=None
                ) - datetime.timedelta(seconds=time.localtime().tm_gmtoff)

            stmt = insert(FilesMeta).values(
                path=os.path.join(
                    self._camera.segments_folder, file.split(".")[0] + ".m4s"
                ),
                orig_ctime=orig_ctime,
                meta={"m3u8": {"EXTINF": extinf}},
            )
            session.execute(stmt)
            session.commit()

    def _read_m3u8_mp4box(self, file: str) -> str:
        """Read m3u8 file created by MP4Box."""
        return open(
            os.path.join(
                self._camera.temp_segments_folder,
                file.split(".")[0],
                "master_1.m3u8",
            ),
            encoding="utf-8",
        ).read()

    def _read_m3u8(self) -> str:
        """Read m3u8 file created by encoder."""
        return open(
            os.path.join(
                self._camera.temp_segments_folder,
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
            os.remove(os.path.join(self._camera.temp_segments_folder, file))
            shutil.rmtree(
                os.path.join(self._camera.temp_segments_folder, file.split(".")[0]),
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
                os.remove(os.path.join(self._camera.temp_segments_folder, file))
        except Exception as err:  # pylint: disable=broad-except
            self._logger.error(f"Failed to process m4s file {file}", exc_info=err)
        finally:
            try:
                os.remove(os.path.join(self._camera.temp_segments_folder, file))
            except FileNotFoundError:
                pass

    def _create_fragmented_mp4(self):
        """Create fragmented mp4 from mp4 using MP4Box."""
        self._logger.debug("Checking for new segments to fragment")
        mp4s = _get_mp4_files_to_fragment(self._camera.temp_segments_folder)
        # Handle max 5 files per iteration to avoid blocking the thread for too long
        for mp4 in sorted(mp4s)[:5]:
            self._logger.debug(f"Processing {mp4}")
            if mp4.split(".")[1] == "m4s":
                self._handle_m4s(mp4)
            else:
                self._handle_mp4(mp4)

    def _shutdown(self) -> None:
        """Handle shutdown event."""
        self._logger.debug("Shutting down fragment thread")
        self._camera.stopped.wait()
        self._logger.debug("Camera stopped, running final fragmentation")
        self._create_fragmented_mp4()
        self._logger.debug("Fragment thread shutdown complete")

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
        self._logger.debug(f"HLS Playlist for contatenation: {playlist}")
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
        except sp.CalledProcessError as err:
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
        playlist.append(f"#EXT-X-TARGETDURATION:{target_duration}")

    playlist.append("#EXT-X-INDEPENDENT-SEGMENTS")
    playlist.append(f'#EXT-X-MAP:URI="{_get_file_path(init_file, file_directive)}"')
    for fragment in fragments:
        playlist.append("#EXT-X-DISCONTINUITY")
        program_date_time = fragment.creation_time.replace(
            tzinfo=datetime.timezone.utc
        ).isoformat(timespec="milliseconds")
        playlist.append(f"#EXT-X-PROGRAM-DATE-TIME:{program_date_time}")
        playlist.append(f"#EXTINF:{fragment.duration},")
        playlist.append(_get_file_path(fragment.path, file_directive))
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
