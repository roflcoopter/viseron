"""Base recorder."""

from __future__ import annotations

import datetime
import logging
import os
import shutil
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import sleep
from typing import TYPE_CHECKING, Any, TypedDict

import cv2
import numpy as np
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from viseron.components.storage.const import COMPONENT as STORAGE_COMPONENT
from viseron.components.storage.models import Recordings
from viseron.components.storage.queries import get_recording_fragments
from viseron.const import CAMERA_SEGMENT_DURATION
from viseron.domains.camera.fragmenter import Fragment
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.events import EventData
from viseron.helpers import create_directory, draw_objects, get_utc_offset, utcnow
from viseron.watchdog.thread_watchdog import RestartableThread

from .const import (
    CONFIG_CREATE_EVENT_CLIP,
    CONFIG_FILENAME_PATTERN,
    CONFIG_IDLE_TIMEOUT,
    CONFIG_LOOKBACK,
    CONFIG_MAX_RECORDING_TIME,
    CONFIG_RECORDER,
    CONFIG_SAVE_TO_DISK,
    CONFIG_THUMBNAIL,
    DEFAULT_LOOKBACK,
    EVENT_RECORDER_COMPLETE,
    EVENT_RECORDER_START,
    EVENT_RECORDER_STOP,
)
from .entity.binary_sensor import RecorderBinarySensor
from .entity.image import ThumbnailImage
from .shared_frames import SharedFrame

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.storage import Storage
    from viseron.components.storage.models import TriggerTypes
    from viseron.domains.camera import AbstractCamera, FailedCamera


class RecordingDict(TypedDict):
    """Recording dict."""

    id: int
    camera_identifier: str
    start_time: datetime.datetime
    start_timestamp: float
    end_time: datetime.datetime | None
    end_timestamp: float | None
    trigger_type: TriggerTypes | None
    trigger_id: int | None
    thumbnail_path: str
    hls_url: str


@dataclass
class EventRecorderData(EventData):
    """Hold information on recorder start/stop/complete event."""

    camera: AbstractCamera
    recording: Recording

    def as_dict(self):
        """Return as dict."""
        return {
            "camera": self.camera,
            "recording": self.recording,
        }


@dataclass
class Recording:
    """Recording dict representation."""

    id: int
    start_time: datetime.datetime
    start_timestamp: float
    end_time: datetime.datetime | None
    end_timestamp: float | None
    date: str
    thumbnail: np.ndarray | None
    thumbnail_path: str | None
    clip_path: str | None
    objects: list[DetectedObject]
    trigger_type: TriggerTypes | None

    def as_dict(self):
        """Return as dict."""
        return {
            "id": self.id,
            "start_time": self.start_time,
            "start_timestamp": self.start_timestamp,
            "end_time": self.end_time,
            "end_timestamp": self.end_timestamp,
            "date": self.date,
            "thumbnail_path": self.thumbnail_path,
            "objects": self.objects,
            "trigger_type": self.trigger_type,
        }

    def get_fragments(
        self, lookback: float, get_session: Callable[[], Session], now=None
    ):
        """Return a list of files for this recording."""
        return get_recording_fragments(self.id, lookback, get_session, now)


@dataclass
class ManualRecording:
    """Dataclass for manual recordings."""

    duration: int | None = None


class RecorderBase:
    """Base recorder."""

    def __init__(
        self,
        vis: Viseron,
        config: dict[str, Any],
        camera: AbstractCamera | FailedCamera,
    ) -> None:
        self._logger = logging.getLogger(self.__module__ + "." + camera.identifier)
        self._vis = vis
        self._config = config
        self._camera = camera

        self._storage: Storage = vis.data[STORAGE_COMPONENT]

    def get_recordings(
        self, utc_offset: datetime.timedelta, date=None, subpath: str = ""
    ) -> dict[str, dict[int, RecordingDict]]:
        """Return all recordings."""
        return get_recordings(
            self._storage.get_session,
            self._camera.identifier,
            utc_offset,
            date=date,
            subpath=subpath,
        )

    def get_latest_recording(
        self, utc_offset: datetime.timedelta, date=None, subpath: str = ""
    ) -> dict[str, dict[int, RecordingDict]]:
        """Return the latest recording."""
        return get_recordings(
            self._storage.get_session,
            self._camera.identifier,
            utc_offset,
            date=date,
            latest=True,
            subpath=subpath,
        )

    def get_latest_recording_daily(
        self, utc_offset: datetime.timedelta, subpath: str = ""
    ) -> dict[str, dict[int, RecordingDict]]:
        """Return the latest recording for each day."""
        return get_recordings(
            self._storage.get_session,
            self._camera.identifier,
            utc_offset,
            latest=True,
            daily=True,
            subpath=subpath,
        )

    def delete_recording(
        self, utc_offset: datetime.timedelta, date=None, recording_id=None
    ) -> bool:
        """Delete a single recording.

        We dont have to delete the segments as they will be deleted by the tier
        handler the next time it runs.
        """
        return bool(
            delete_recordings(
                self._storage.get_session,
                self._camera.identifier,
                utc_offset,
                date=date,
                recording_id=recording_id,
            )
        )

    @property
    @abstractmethod
    def lookback(self) -> int:
        """Return lookback."""


class AbstractRecorder(ABC, RecorderBase):
    """Abstract recorder."""

    def __init__(self, vis: Viseron, component, config, camera: AbstractCamera) -> None:
        super().__init__(vis, config, camera)
        self._storage: Storage = vis.data[STORAGE_COMPONENT]
        self._camera: AbstractCamera = camera

        self.is_recording = False
        self._active_recording: Recording | None = None

        create_directory(self._camera.event_clips_folder)
        create_directory(self._camera.segments_folder)
        create_directory(self._camera.temp_segments_folder)
        create_directory(self._camera.thumbnails_folder)

        vis.add_entity(component, RecorderBinarySensor(vis, self._camera))
        vis.add_entity(component, ThumbnailImage(vis, self._camera))

    def as_dict(self) -> dict[str, dict[int, RecordingDict]]:
        """Return recorder information as dict."""
        return self.get_recordings(get_utc_offset())

    def create_thumbnail(
        self,
        recording_id: int,
        frame: np.ndarray,
        objects: list[DetectedObject],
    ) -> tuple[np.ndarray, str]:
        """Create thumbnails, sent to MQTT and/or saved to disk based on config."""
        self._logger.debug(f"Saving thumbnail in {self._camera.thumbnails_folder}")
        thumbnail_name = f"{recording_id}.jpg"
        thumbnail_path = os.path.join(self._camera.thumbnails_folder, thumbnail_name)

        if objects:
            draw_objects(
                frame,
                objects,
            )
        if not cv2.imwrite(thumbnail_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100]):
            self._logger.error(f"Failed saving thumbnail {thumbnail_path} to disk")

        if self._config[CONFIG_RECORDER][CONFIG_THUMBNAIL][CONFIG_SAVE_TO_DISK]:
            if not cv2.imwrite(
                os.path.join(self._camera.thumbnails_folder, "latest_thumbnail.jpg"),
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), 100],
            ):
                self._logger.error("Failed saving latest_thumbnail.jpg to disk")
        return frame, thumbnail_path

    def start(
        self,
        shared_frame: SharedFrame,
        objects_in_fov: list[DetectedObject],
        trigger_type: TriggerTypes,
    ) -> Recording:
        """Start recording."""
        self._logger.info("Starting recorder")
        self.is_recording = True
        start_time = utcnow()

        with self._storage.get_session() as session:
            stmt = (
                insert(Recordings)
                .values(
                    camera_identifier=self._camera.identifier,
                    trigger_type=trigger_type,
                    start_time=start_time,
                    adjusted_start_time=start_time
                    - datetime.timedelta(seconds=self.lookback)
                    - datetime.timedelta(seconds=CAMERA_SEGMENT_DURATION),
                )
                .returning(Recordings.id)
            )
            result = session.execute(stmt).scalars()
            recording_id = result.one()
            thumbnail, thumbnail_path = self.create_thumbnail(
                recording_id,
                self._camera.shared_frames.get_decoded_frame_rgb(shared_frame).copy(),
                objects_in_fov,
            )
            stmt2 = (
                update(Recordings)
                .values(
                    thumbnail_path=thumbnail_path,
                )
                .where(Recordings.id == recording_id)
            )
            session.execute(stmt2)
            session.commit()

        recording = Recording(
            id=recording_id,
            start_time=start_time,
            start_timestamp=start_time.timestamp(),
            end_time=None,
            end_timestamp=None,
            date=start_time.date().isoformat(),
            thumbnail=thumbnail,
            thumbnail_path=(
                thumbnail_path
                if self._config[CONFIG_RECORDER][CONFIG_THUMBNAIL][CONFIG_SAVE_TO_DISK]
                else None
            ),
            clip_path=None,
            objects=objects_in_fov,
            trigger_type=trigger_type,
        )

        self._start(recording, shared_frame, objects_in_fov)
        self._active_recording = recording
        self._vis.dispatch_event(
            EVENT_RECORDER_START.format(camera_identifier=self._camera.identifier),
            EventRecorderData(
                camera=self._camera,
                recording=recording,
            ),
        )
        return recording

    @abstractmethod
    def _start(
        self,
        recording: Recording,
        shared_frame: SharedFrame,
        objects_in_fov: list[DetectedObject],
    ):
        """Start the recorder."""

    def stop(self, recording: Recording | None) -> None:
        """Stop recording."""
        self._logger.info("Stopping recorder")
        if recording is None:
            self._logger.error("No active recording to stop")
            return

        end_time = utcnow()
        recording.end_time = end_time
        recording.end_timestamp = end_time.timestamp()

        with self._storage.get_session() as session:
            stmt = (
                update(Recordings)
                .where(Recordings.id == recording.id)
                .values(
                    end_time=recording.end_time,
                )
            )
            session.execute(stmt)
            session.commit()

        self._stop(recording)
        self._active_recording = None
        self._vis.dispatch_event(
            EVENT_RECORDER_STOP.format(camera_identifier=self._camera.identifier),
            EventRecorderData(
                camera=self._camera,
                recording=recording,
            ),
        )
        self.is_recording = False

        if self._config[CONFIG_RECORDER][CONFIG_CREATE_EVENT_CLIP]:
            concat_thread = RestartableThread(
                name=f"viseron.camera.{self._camera.identifier}.concatenate_fragments",
                target=self._concatenate_fragments,
                args=(recording,),
                register=False,
            )
            concat_thread.start()

    def video_name(self, start_time: datetime.datetime) -> str:
        """Return video name."""
        filename_pattern = (start_time + get_utc_offset()).strftime(
            self._config[CONFIG_RECORDER][CONFIG_FILENAME_PATTERN]
        )
        return f"{filename_pattern}.{self._camera.extension}"

    def _concatenate_fragments(self, recording: Recording) -> int | None:
        sleep(CAMERA_SEGMENT_DURATION * 2)  # include segments still being written to
        files = recording.get_fragments(
            self.lookback,
            self._storage.get_session,
        )
        fragments = [
            Fragment(file.filename, file.path, file.duration, file.orig_ctime)
            for file in files
        ]
        num_fragments = len(fragments)
        if num_fragments == 0:
            self._logger.error("No fragments available.")
            return None
        event_clip = self._camera.fragmenter.concatenate_fragments(fragments)
        if not event_clip:
            return None

        # Create filename
        video_name = self.video_name(recording.start_time)

        # Create foldername
        full_path = os.path.join(
            self._camera.event_clips_folder, recording.start_time.date().isoformat()
        )

        clip_path = os.path.join(full_path, video_name)

        create_directory(os.path.dirname(clip_path))
        shutil.move(
            event_clip,
            clip_path,
        )
        self._logger.debug(f"Moved event clip to {clip_path}")

        with self._storage.get_session() as session:
            stmt = (
                update(Recordings)
                .where(Recordings.id == recording.id)
                .values(
                    clip_path=clip_path,
                )
            )
            session.execute(stmt)
            session.commit()

        recording.clip_path = clip_path
        self._vis.dispatch_event(
            EVENT_RECORDER_COMPLETE.format(camera_identifier=self._camera.identifier),
            EventRecorderData(
                camera=self._camera,
                recording=recording,
            ),
        )

        return num_fragments

    @abstractmethod
    def _stop(self, recording: Recording):
        """Stop the recorder."""

    @property
    def idle_timeout(self):
        """Return idle timeout."""
        return self._config[CONFIG_RECORDER][CONFIG_IDLE_TIMEOUT]

    @property
    def active_recording(self) -> Recording | None:
        """Return active recording."""
        return self._active_recording

    @property
    def lookback(self) -> int:
        """Return lookback."""
        return self._config[CONFIG_RECORDER][CONFIG_LOOKBACK]

    @property
    def max_recording_time(self) -> int:
        """Return max_recording_time."""
        return self._config[CONFIG_RECORDER][CONFIG_MAX_RECORDING_TIME]

    @property
    def max_recording_time_exceeded(self) -> bool:
        """Return True if the maximum recording time has been exceeded."""
        if self._active_recording is None:
            return False
        return (
            utcnow() - self._active_recording.start_time
        ).total_seconds() > self.max_recording_time


class FailedCameraRecorder(RecorderBase):
    """Failed camera recorder.

    Provides access to the recordings for failed cameras.
    """

    @property
    def lookback(self) -> int:
        """Return lookback."""
        return self._config.get(CONFIG_RECORDER, {}).get(
            CONFIG_LOOKBACK, DEFAULT_LOOKBACK
        )


def get_recordings(
    get_session: Callable[[], Session],
    camera_identifier: str,
    utc_offset: datetime.timedelta,
    date: str | None = None,
    latest: bool = False,
    daily: bool = False,
    subpath: str = "",
) -> dict[str, dict[int, RecordingDict]]:
    """Return all recordings using PostgreSQL UTC offset conversion.

    Args:
        get_session: Callable that returns a database session
        camera_identifier: Identifier for the camera
        utc_offset: User's UTC offset as timedelta (e.g., timedelta(hours=-5))
        date: Optional date filter in user's local timezone (YYYY-MM-DD)
        latest: If True, return only the most recent recording(s)
        daily: If True and latest is True, return the latest recording for each day
        subpath: Subpath prefix for URLs (e.g., '/viseron')

    Returns:
        Dictionary of recordings organized by date in user's local timezone
    """
    recordings: dict[str, dict[int, RecordingDict]] = {}

    local_timestamp = Recordings.start_time.local(utc_offset)
    local_date = func.date(local_timestamp).label("local_date")

    stmt = (
        select(Recordings, local_date)
        .where(Recordings.camera_identifier == camera_identifier)
        .order_by(local_date.desc(), local_timestamp.desc())
    )
    if date:
        stmt = stmt.where(local_date == date)

    if latest and daily:
        stmt = stmt.distinct(local_date)
    elif latest:
        stmt = stmt.limit(1)

    with get_session() as session:
        for row in session.execute(stmt):
            recording = row.Recordings
            _local_date = row.local_date.isoformat()

            if _local_date not in recordings:
                recordings[_local_date] = {}

            recordings[_local_date][recording.id] = _recording_file_dict(
                recording, subpath
            )

    return recordings


def delete_recordings(
    get_session: Callable[[], Session],
    camera_identifier,
    utc_offset: datetime.timedelta,
    date=None,
    recording_id=None,
) -> Sequence[Recordings]:
    """Delete recordings from the database.

    Returns the deleted recordings so that they can be deleted from disk.
    """
    stmt = (
        delete(Recordings)
        .where(Recordings.camera_identifier == camera_identifier)
        .returning(Recordings)
    )
    if date:
        stmt = stmt.where(func.date(Recordings.start_time.local(utc_offset)) == date)
    if recording_id:
        stmt = stmt.where(Recordings.id == recording_id)
    with get_session() as session:
        _deleted_recordings = session.execute(stmt).scalars().all()
        session.commit()
    return _deleted_recordings


def _recording_file_dict(recording: Recordings, subpath: str = "") -> RecordingDict:
    """Return a dict with recording file information."""
    return {
        "id": recording.id,
        "camera_identifier": recording.camera_identifier,
        "start_time": recording.start_time,
        "start_timestamp": recording.start_time.timestamp(),
        "end_time": recording.end_time,
        "end_timestamp": recording.end_time.timestamp() if recording.end_time else None,
        "trigger_type": recording.trigger_type,
        "trigger_id": recording.trigger_id,
        "thumbnail_path": f"{subpath}/files{recording.thumbnail_path}",
        "hls_url": (
            # pylint: disable=line-too-long
            f"{subpath}/api/v1/hls/{recording.camera_identifier}/{recording.id}/index.m3u8"
        ),
    }
