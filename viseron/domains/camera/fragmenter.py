"""Convert MP4 to fragmented MP4 for streaming."""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess as sp
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
    mp4_files = Path(path).walkfiles("*.mp4")
    files_in_use = []
    for process in psutil.process_iter():
        try:
            process_name = process.name()
            if any(pattern in process_name for pattern in ["ffmpeg", "gstreamer"]):
                files_in_use.extend(_get_open_files(path, process))
        except psutil.Error:
            pass
    return [str(f.name) for f in mp4_files if str(f.name) not in files_in_use]


def _extract_extinf_number(text) -> float | None:
    """Extract the EXTINF number from a HLS playlist."""
    pattern = r"#EXTINF:(\d+\.\d+),"
    match = re.search(pattern, text)
    if match:
        return float(match.group(1))
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
            self._create_fragmented_mp4, "interval", seconds=5, id=self._fragment_job_id
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
            self._logger.error(err)
            return False
        return True

    def _move_to_segments_folder(self, file: str):
        """Move fragmented mp4 to segments folder."""
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

    def _write_files_metadata(self, file: str):
        """Write metadata about the fragmented mp4 to the database."""
        extinf = _extract_extinf_number(
            open(
                os.path.join(
                    self._camera.temp_segments_folder,
                    file.split(".")[0],
                    "master_1.m3u8",
                ),
                encoding="utf-8",
            ).read()
        )
        with self._storage.get_session() as session:
            stmt = insert(FilesMeta).values(
                path=os.path.join(
                    self._camera.segments_folder, file.split(".")[0] + ".m4s"
                ),
                meta={"m3u8": {"EXTINF": extinf}},
            )
            session.execute(stmt)
            session.commit()

    def _create_fragmented_mp4(self):
        """Create fragmented mp4 from mp4 using MP4Box."""
        self._logger.debug("Checking for new segments to fragment")
        mp4s = _get_mp4_files_to_fragment(self._camera.temp_segments_folder)
        for mp4 in sorted(mp4s):
            self._logger.debug(f"Processing {mp4}")
            if self._mp4box_command(mp4):
                self._write_files_metadata(mp4)
                self._move_to_segments_folder(mp4)
            os.remove(os.path.join(self._camera.temp_segments_folder, mp4))
            shutil.rmtree(
                os.path.join(self._camera.temp_segments_folder, mp4.split(".")[0])
            )

    def _shutdown(self) -> None:
        """Handle shutdown event."""
        self._logger.debug("Shutting down fragment thread")
        self._camera.stopped.wait()
        self._logger.debug("Camera stopped, running final fragmentation")
        self._create_fragmented_mp4()
        self._logger.debug("Fragment thread shutdown complete")

    def concatenate_fragments(
        self, fragments: list[Fragment], sequence_number=0
    ) -> str | Literal[False]:
        """Concatenate fragments into a single mp4 file."""
        filename = os.path.join(TEMP_DIR, f"{str(uuid.uuid4())}.mp4")
        playlist = generate_playlist(
            fragments,
            os.path.join(self._camera.segments_folder, "init.mp4"),
            sequence_number=sequence_number,
            end=True,
            file_directive=True,
        )
        self._logger.debug(f"HLS Playlist for contatenation: {playlist}")
        try:
            sp.run(  # type: ignore[call-overload]
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-i",
                    "-",
                    "-acodec",
                    "copy",
                    "-vcodec",
                    "copy",
                    filename,
                ],
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
    sequence_number=0,
    end=False,
    file_directive=False,
) -> str:
    """Generate a playlist from a list of fragments."""
    playlist = []
    playlist.append("#EXTM3U")
    playlist.append("#EXT-X-VERSION:6")

    playlist.append(f"#EXT-X-MEDIA-SEQUENCE:{sequence_number}")
    if sequence_number:
        playlist.append(f"#EXT-X-DISCONTINUITY-SEQUENCE:{sequence_number}")

    if fragments:
        target_duration = ceil(max(f.duration for f in fragments))
        playlist.append(f"#EXT-X-TARGETDURATION:{target_duration}")

    playlist.append("#EXT-X-INDEPENDENT-SEGMENTS")
    playlist.append(f'#EXT-X-MAP:URI="{_get_file_path(init_file, file_directive)}"')
    for fragment in fragments:
        playlist.append(f"#EXTINF:{fragment.duration},")
        playlist.append(_get_file_path(fragment.path, file_directive))
        playlist.append("#EXT-X-DISCONTINUITY")
    if end:
        playlist.append("#EXT-X-ENDLIST")
    return "\n".join(playlist)


@dataclass
class Fragment:
    """Represents a fragment of a mp4 file."""

    path: str
    duration: float
