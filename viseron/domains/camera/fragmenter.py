"""Convert MP4 to fragmented MP4 for streaming."""

from __future__ import annotations

import datetime
import logging
import os
import queue
import subprocess as sp
import threading
import uuid
from dataclasses import dataclass
from math import ceil
from typing import TYPE_CHECKING, Literal, TypedDict

from apscheduler.jobstores.base import JobLookupError

from viseron.components.storage.const import (
    COMPONENT as STORAGE_COMPONENT,
    EVENT_CHECK_TIER,
    TIER_CATEGORY_RECORDER,
    TIER_SUBCATEGORY_SEGMENTS,
    CleanupJobNames,
)
from viseron.components.storage.models import FilesMeta
from viseron.components.storage.queries import get_time_period_fragments
from viseron.const import CAMERA_SEGMENT_DURATION, TEMP_DIR, VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera.const import CONFIG_FFMPEG_LOGLEVEL, CONFIG_RECORDER
from viseron.domains.camera.fragmenter_process import FragmenterWork
from viseron.events import EventEmptyData
from viseron.helpers.child_process_context import get_child_process_context
from viseron.helpers.child_process_worker import ChildProcessWorker
from viseron.helpers.logs import LogPipe

if TYPE_CHECKING:
    from collections.abc import Callable

    from apscheduler.schedulers.base import Job
    from sqlalchemy.orm import Session

    from viseron import Viseron
    from viseron.components.storage import Storage
    from viseron.domains.camera import AbstractCamera

FRAGMENTER_DRAIN_TIMEOUT = CAMERA_SEGMENT_DURATION * 2


class FragmenterSubProcessWorker(ChildProcessWorker):
    """Child process worker for running fragmentation in a child process."""

    def __init__(
        self,
        vis: Viseron,
        storage: Storage,
        camera: AbstractCamera,
        temp_segments_folder: str,
        segments_folder: str,
        metadata_callback: Callable[[dict], None],
    ) -> None:
        self._vis = vis
        self._storage = storage
        self._camera = camera
        self._worker_event = get_child_process_context().Event()
        self._drained = threading.Event()
        self.on_metadata = metadata_callback
        # Fragmenter owns the stop so it can drain pending segments first
        super().__init__(
            vis,
            f"fragmenter.{camera.identifier}",
            FragmenterWork(
                camera.identifier,
                temp_segments_folder,
                segments_folder,
                camera.timelapse_folder,
                camera.temp_timelapse_folder,
                self._worker_event,
            ),
            stop_on_shutdown=False,
        )

    def drain(self, timeout: float) -> bool:
        """Fragment all pending segments, blocking until done or timeout."""
        self._drained.clear()
        try:
            self.input_queue.put({"cmd": "drain"}, timeout=timeout)
        except queue.Full:
            return False
        return self._drained.wait(timeout)

    def work_output(self, item: dict | None) -> None:
        """Relay metadata from child process to main process via callback."""
        if item is None:
            return

        if item.get("drained"):
            self._drained.set()
            return

        if item.get("error") == "no_space_left":
            self._vis.dispatch_event(
                EVENT_CHECK_TIER.format(
                    camera_identifier=self._camera.identifier,
                    tier_id=0,
                    category=TIER_CATEGORY_RECORDER,
                    subcategory=TIER_SUBCATEGORY_SEGMENTS,
                ),
                EventEmptyData(),
                store=False,
            )
            self._storage.cleanup_manager.run_job(CleanupJobNames.ORPHANED_FILES)

        if "path" in item:
            self.on_metadata(item)

        self._worker_event.set()


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
        self._storage = vis.data[STORAGE_COMPONENT]
        os.makedirs(camera.temp_segments_folder, exist_ok=True)
        if camera.temp_timelapse_folder is not None:
            os.makedirs(camera.temp_timelapse_folder, exist_ok=True)
        self._storage.ignore_file("init.mp4")

        self._log_pipe_ffmpeg = LogPipe(
            logging.getLogger(f"{self.__module__}.{camera.identifier}.ffmpeg"),
            logging.ERROR,
        )

        self._lock = threading.Lock()
        self._fragment_worker: FragmenterSubProcessWorker | None = None
        self._fragment_job: Job | None = None
        self._fragment_job_id = f"fragment_{self._camera.identifier}"
        self._event_listeners = []
        self._event_listeners.append(
            vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self._shutdown)
        )

    def start(self) -> None:
        """Start the fragmentation child process and the job that feeds it."""
        with self._lock:
            if self._fragment_worker is not None:
                return

            self._logger.debug("Starting fragmenter")
            # A ChildProcessWorker cannot be restarted once stopped
            self._fragment_worker = FragmenterSubProcessWorker(
                self._vis,
                self._storage,
                self._camera,
                self._camera.temp_segments_folder,
                self._camera.segments_folder,
                self._on_metadata_from_worker,
            )
            self._fragment_job = self._vis.background_scheduler.add_job(
                self._fragment_command,
                "interval",
                seconds=1,
                id=self._fragment_job_id,
                max_instances=1,
                coalesce=True,
                replace_existing=True,
            )

    def stop(self) -> None:
        """Stop the fragmentation child process and the job that feeds it."""
        with self._lock:
            if self._fragment_worker is None:
                return

            self._logger.debug("Stopping fragmenter")
            if self._fragment_job is not None:
                try:
                    self._fragment_job.remove()
                except JobLookupError:
                    pass
                except Exception:  # pylint: disable=broad-except
                    self._logger.exception("Failed to remove fragment job.")
                self._fragment_job = None

            # Recordings stopped along with the camera need their last segments
            if not self._fragment_worker.drain(timeout=FRAGMENTER_DRAIN_TIMEOUT):
                self._logger.warning("Timed out fragmenting remaining segments")
            self._fragment_worker.stop()
            self._fragment_worker = None

    def _on_metadata_from_worker(self, item) -> None:
        """Update temporary_files_meta with metadata from subprocess."""
        self._storage.temporary_files_meta[item["path"]] = FilesMeta(
            orig_ctime=item["orig_ctime"], duration=item["duration"]
        )

    def _fragment_command(self) -> None:
        """Periodically send work to the subprocess."""
        # Local reference since stop() may clear the worker from another thread
        worker = self._fragment_worker
        if worker is None or self._camera.stopped.is_set():
            return

        try:
            worker.input_queue.put({"cmd": "fragment"}, timeout=1)
        except queue.Full:
            pass

    def _shutdown(self) -> None:
        """Handle shutdown event."""
        self._logger.debug("Shutting down fragment thread")
        if not self._camera.stopped.is_set():
            self._camera.stopped.wait(timeout=5)
        self.stop()
        self._log_pipe_ffmpeg.close()

    def unload(self) -> None:
        """Unload fragmenter."""
        self._logger.debug("Unloading fragmenter")
        self._shutdown()
        for unsubscribe in self._event_listeners:
            unsubscribe()

    def concatenate_fragments(
        self, fragments: list[Fragment], media_sequence: int = 0
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
        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            self._camera.config[CONFIG_RECORDER][CONFIG_FFMPEG_LOGLEVEL],
            "-f",
            "hls",
            "-protocol_whitelist",
            "file,pipe,fd",
            "-i",
            "-",
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            filename,
        ]
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


def get_skipped_segment_count(fragments: list[Fragment], skip_boundary: float) -> int:
    """Get the number of fragments a Playlist Delta Update can skip.

    Fragments are kept from the end of the playlist until they cover the skip
    boundary, everything before them is skipped.
    """
    kept_duration = 0.0
    for index in range(len(fragments) - 1, -1, -1):
        if kept_duration >= skip_boundary:
            return index + 1
        kept_duration += fragments[index].duration
    return 0


def generate_playlist(
    fragments: list[Fragment],
    init_file: str,
    media_sequence: int = 0,
    target_duration: int | None = None,
    *,
    end: bool = False,
    file_directive: bool = False,
    can_skip_until: float | None = None,
    max_skipped_segments: int = 0,
) -> str:
    """Generate a playlist from a list of fragments.

    If can_skip_until is set, Playlist Delta Updates are advertised, and up to
    max_skipped_segments of the fragments older than the skip boundary are replaced
    by EXT-X-SKIP. Both are ignored for ended playlists.
    """
    skipped = 0
    if can_skip_until is not None and not end:
        skipped = min(
            get_skipped_segment_count(fragments, can_skip_until), max_skipped_segments
        )

    playlist = []
    playlist.append("#EXTM3U")
    # EXT-X-SKIP requires compatibility version 9
    playlist.append(f"#EXT-X-VERSION:{9 if skipped else 6}")

    playlist.append(f"#EXT-X-MEDIA-SEQUENCE:{media_sequence}")
    if media_sequence:
        playlist.append(f"#EXT-X-DISCONTINUITY-SEQUENCE:{media_sequence}")

    if target_duration:
        pass
    elif fragments and target_duration is None:
        target_duration = ceil(max(f.duration for f in fragments))
        target_duration = max(target_duration, CAMERA_SEGMENT_DURATION)
    else:
        target_duration = CAMERA_SEGMENT_DURATION

    playlist.append(f"#EXT-X-TARGETDURATION:{target_duration}")
    if can_skip_until is not None and not end:
        playlist.append(f"#EXT-X-SERVER-CONTROL:CAN-SKIP-UNTIL={can_skip_until}")
    playlist.append("#EXT-X-INDEPENDENT-SEGMENTS")
    if skipped:
        playlist.append(f"#EXT-X-SKIP:SKIPPED-SEGMENTS={skipped}")
    playlist.append(f'#EXT-X-MAP:URI="{_get_file_path(init_file, file_directive)}"')

    # Compare against the last skipped fragment so a gap right after it is kept
    prev_fragment: Fragment | None = fragments[skipped - 1] if skipped else None
    for fragment in fragments[skipped:]:
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
    time_from: float,
    time_to: float | None = None,
) -> list[Timespan]:
    """Get the available timespans of HLS fragments for a time period."""
    files = get_time_period_fragments(
        camera_identifiers, time_from, time_to, get_session
    )
    spans: list[tuple[float, float]] = []
    for file in files:
        file_start = file.orig_ctime.timestamp()
        file_end = file_start + file.duration
        if spans and file_start <= spans[-1][1] + file.duration:
            spans[-1] = (spans[-1][0], file_end)
        else:
            spans.append((file_start, file_end))
    return [
        {"start": int(start), "end": int(end), "duration": int(end - start)}
        for start, end in spans
    ]
