"""Base recorder."""
from __future__ import annotations

import datetime
import logging
import os
import shutil
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

import cv2
import numpy as np
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from viseron.components.storage.const import COMPONENT as STORAGE_COMPONENT
from viseron.components.storage.models import Recordings
from viseron.components.storage.queries import get_recording_fragments
from viseron.domains.camera.fragmenter import Fragment
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.events import EventData
from viseron.helpers import create_directory, draw_objects, utcnow

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
    from viseron.domains.camera import AbstractCamera, FailedCamera


class RecordingDict(TypedDict):
    """Recording dict."""

    id: int
    camera_identifier: str
    start_time: datetime.datetime
    start_timestamp: float
    end_time: datetime.datetime | None
    end_timestamp: float | None
    date: str
    trigger_type: str | None
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
    path: str
    filename: str
    thumbnail: np.ndarray | None
    thumbnail_path: str | None
    objects: list[DetectedObject]

    def as_dict(self):
        """Return as dict."""
        return {
            "id": self.id,
            "start_time": self.start_time,
            "start_timestamp": self.start_timestamp,
            "end_time": self.end_time,
            "end_timestamp": self.end_timestamp,
            "date": self.date,
            "path": self.path,
            "filename": self.filename,
            "thumbnail_path": self.thumbnail_path,
            "objects": self.objects,
        }

    def get_fragments(
        self, lookback: float, get_session: Callable[[], Session], now=None
    ):
        """Return a list of files for this recording."""
        return get_recording_fragments(self.id, lookback, get_session, now)


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

    def get_recordings(self, date=None) -> dict[str, dict[int, RecordingDict]]:
        """Return all recordings."""
        return get_recordings(self._storage.get_session, self._camera.identifier, date)

    def get_latest_recording(self, date=None) -> dict[str, dict[int, RecordingDict]]:
        """Return the latest recording."""
        return get_recordings(
            self._storage.get_session, self._camera.identifier, date, latest=True
        )

    def get_latest_recording_daily(self) -> dict[str, dict[int, RecordingDict]]:
        """Return the latest recording for each day."""
        return get_recordings(
            self._storage.get_session, self._camera.identifier, latest=True, daily=True
        )

    def delete_recording(self, date=None, recording_id=None) -> bool:
        """Delete a single recording.

        We dont have to delete the segments as they will be deleted by the tier
        handler the next time it runs.
        """
        return bool(
            delete_recordings(
                self._storage.get_session,
                self._camera.identifier,
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

        create_directory(self._camera.recordings_folder)
        create_directory(self._camera.segments_folder)
        create_directory(self._camera.temp_segments_folder)
        create_directory(self._camera.thumbnails_folder)

        vis.add_entity(component, RecorderBinarySensor(vis, self._camera))
        vis.add_entity(component, ThumbnailImage(vis, self._camera))

    def as_dict(self) -> dict[str, dict[int, RecordingDict]]:
        """Return recorder information as dict."""
        return self.get_recordings()

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
    ) -> Recording:
        """Start recording."""
        self._logger.info("Starting recorder")
        self.is_recording = True
        start_time = utcnow()

        # Create filename
        filename_pattern = start_time.strftime(
            self._config[CONFIG_RECORDER][CONFIG_FILENAME_PATTERN]
        )
        video_name = f"{filename_pattern}.{self._camera.extension}"

        # Create foldername
        full_path = os.path.join(
            self._camera.recordings_folder, start_time.date().isoformat()
        )
        create_directory(full_path)

        with self._storage.get_session() as session:
            stmt = (
                insert(Recordings)
                .values(
                    camera_identifier=self._camera.identifier,
                    start_time=start_time,
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
            path=os.path.join(full_path, video_name),
            filename=video_name,
            thumbnail=thumbnail,
            thumbnail_path=thumbnail_path
            if self._config[CONFIG_RECORDER][CONFIG_THUMBNAIL][CONFIG_SAVE_TO_DISK]
            else None,
            objects=objects_in_fov,
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
            concat_thread = threading.Thread(
                target=self._concatenate_fragments, args=(recording,)
            )
            concat_thread.start()

    def _concatenate_fragments(self, recording: Recording) -> None:
        files = recording.get_fragments(
            self.lookback,
            self._storage.get_session,
        )
        fragments = [
            Fragment(
                file.filename, file.path, file.meta["m3u8"]["EXTINF"], file.orig_ctime
            )
            for file in files
            if file.meta.get("m3u8", False).get("EXTINF", False)
        ]
        event_clip = self._camera.fragmenter.concatenate_fragments(fragments)
        if not event_clip:
            return

        shutil.move(
            event_clip,
            recording.path,
        )
        self._logger.debug(f"Moved event clip to {recording.path}")

        with self._storage.get_session() as session:
            stmt = (
                update(Recordings)
                .where(Recordings.id == recording.id)
                .values(
                    clip_path=recording.path,
                )
            )
            session.execute(stmt)
            session.commit()

        self._vis.dispatch_event(
            EVENT_RECORDER_COMPLETE,
            EventRecorderData(
                camera=self._camera,
                recording=recording,
            ),
        )

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
    camera_identifier,
    date=None,
    latest=False,
    daily=False,
) -> dict[str, dict[int, RecordingDict]]:
    """Return all recordings."""
    recordings: dict[str, dict[int, RecordingDict]] = {}
    stmt = (
        select(Recordings)
        .where(Recordings.camera_identifier == camera_identifier)
        .order_by(func.DATE(Recordings.start_time).desc(), Recordings.start_time.desc())
    )
    if date:
        stmt = stmt.where(func.DATE(Recordings.start_time) == date)
    if latest and daily:
        stmt = stmt.distinct(func.DATE(Recordings.start_time))
    elif latest:
        stmt = stmt.limit(1)
    with get_session() as session:
        for recording in session.execute(stmt).scalars():
            if recording.start_time.date().isoformat() not in recordings:
                recordings[recording.start_time.date().isoformat()] = {}
            recordings[recording.start_time.date().isoformat()][
                recording.id
            ] = _recording_file_dict(recording)

    return recordings


def delete_recordings(
    get_session: Callable[[], Session],
    camera_identifier,
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
        stmt = stmt.where(func.DATE(Recordings.start_time) == date)
    if recording_id:
        stmt = stmt.where(Recordings.id == recording_id)
    with get_session() as session:
        _deleted_recordings = session.execute(stmt).scalars().all()
        session.commit()
    return _deleted_recordings


def _recording_file_dict(recording: Recordings) -> RecordingDict:
    """Return a dict with recording file information."""
    return {
        "id": recording.id,
        "camera_identifier": recording.camera_identifier,
        "start_time": recording.start_time,
        "start_timestamp": recording.start_time.timestamp(),
        "end_time": recording.end_time,
        "end_timestamp": recording.end_time.timestamp() if recording.end_time else None,
        "date": recording.start_time.date().isoformat(),
        "trigger_type": recording.trigger_type,
        "trigger_id": recording.trigger_id,
        "thumbnail_path": f"/files{recording.thumbnail_path}",
        "hls_url": (
            f"/api/v1/hls/{recording.camera_identifier}/{recording.id}/index.m3u8"
        ),
    }
