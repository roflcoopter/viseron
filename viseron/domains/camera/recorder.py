"""Base recorder."""
from __future__ import annotations

import datetime
import logging
import os
import shutil
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, TypedDict

import cv2
import numpy as np
from path import Path
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from viseron.components.storage.const import COMPONENT as STORAGE_COMPONENT
from viseron.components.storage.models import Files, FilesMeta, Recordings
from viseron.domains.camera.fragmenter import Fragment
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.helpers import create_directory, draw_objects

from .const import (
    CONFIG_CREATE_EVENT_CLIP,
    CONFIG_FILENAME_PATTERN,
    CONFIG_IDLE_TIMEOUT,
    CONFIG_LOOKBACK,
    CONFIG_RECORDER,
    CONFIG_SAVE_TO_DISK,
    CONFIG_THUMBNAIL,
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
    end_time: datetime.datetime
    end_timestamp: float
    date: str
    trigger_type: str
    trigger_id: int
    thumbnail_path: str


@dataclass
class EventRecorderData:
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

    def get_fragments(self, lookback: int, get_session: Callable[[], Session]):
        """Return a list of files for this recording.

        We must sort on the filename and not created_at as the created_at timestamp is
        not accurate for m4s files that are created from the original mp4 file after
        it has been recorded. The filename is the timestamp of the original mp4 file
        and is therefore accurate.
        """
        if self.end_timestamp is None:
            raise ValueError("Recording has not ended yet")

        start: float = self.start_timestamp - lookback
        with get_session() as session:
            stmt = (
                select(
                    Files.tier_id,
                    Files.camera_identifier,
                    Files.category,
                    Files.path,
                    Files.directory,
                    Files.filename,
                    Files.size,
                    Files.created_at,
                    Files.updated_at,
                    FilesMeta.meta,
                )
                .join(
                    Recordings, Files.camera_identifier == Recordings.camera_identifier
                )
                .join(FilesMeta, Files.path == FilesMeta.path)
                .where(Recordings.id == self.id)
                .where(Files.category == "recorder")
                .where(Files.path.endswith(".m4s"))
                .where(
                    func.substr(Files.filename, 1, 10).between(
                        str(int(start)), str(int(self.end_timestamp))
                    ),
                )
                .order_by(Files.filename.asc())
            )
            fragments = list(session.execute(stmt).fetchall())
        return fragments


class RecorderBase:
    """Base recorder."""

    def __init__(
        self, vis: Viseron, config, camera: AbstractCamera | FailedCamera
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

    def delete_recording(self, date=None, filename=None) -> bool:
        """Delete a single recording."""
        path = None

        if date and filename:
            path = os.path.join(self._camera.recordings_folder, date, filename)
        elif date and filename is None:
            path = os.path.join(self._camera.recordings_folder, date)
        elif date is None and filename is None:
            path = self._camera.recordings_folder
        else:
            self._logger.error("Could not remove file, incorrect path given")
            return False

        self._logger.debug(f"Removing {path}")
        try:
            if filename:
                os.remove(path)
                thumbnail = Path(
                    os.path.join(
                        self._camera.recordings_folder,
                        date,
                        filename.split(".")[0] + ".jpg",
                    )
                )
                try:
                    os.remove(thumbnail)
                except FileNotFoundError:
                    pass

            elif date:
                shutil.rmtree(path)

            else:
                dirs = Path(self._camera.recordings_folder)
                folders = dirs.walkdirs("*-*-*")
                for folder in folders:
                    shutil.rmtree(folder)
        except (OSError, FileNotFoundError) as error:
            self._logger.error(f"Could not remove {path}", exc_info=error)
            return False
        return True


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
        start_time: datetime.datetime,
        frame: np.ndarray,
        objects: list[DetectedObject],
        resolution: tuple[int, int],
    ) -> tuple[np.ndarray, str]:
        """Create thumbnails, sent to MQTT and/or saved to disk based on config."""
        self._logger.debug(f"Saving thumbnail in {self._camera.thumbnails_folder}")
        thumbnail_name = start_time.strftime(
            self._config[CONFIG_RECORDER][CONFIG_THUMBNAIL][CONFIG_FILENAME_PATTERN]
        )
        thumbnail_name = f"{thumbnail_name}.jpg"
        thumbnail_path = os.path.join(self._camera.thumbnails_folder, thumbnail_name)

        draw_objects(
            frame,
            objects,
            resolution,
        )
        if not cv2.imwrite(thumbnail_path, frame):
            self._logger.error(f"Failed saving thumbnail {thumbnail_path} to disk")

        if self._config[CONFIG_RECORDER][CONFIG_THUMBNAIL][CONFIG_SAVE_TO_DISK]:
            if not cv2.imwrite(
                os.path.join(self._camera.thumbnails_folder, "latest_thumbnail.jpg"),
                frame,
            ):
                self._logger.error("Failed saving latest_thumbnail.jpg to disk")
        return frame, thumbnail_path

    def start(
        self,
        shared_frame: SharedFrame,
        objects_in_fov: list[DetectedObject],
        resolution: tuple[int, int],
    ) -> Recording:
        """Start recording."""
        self._logger.info("Starting recorder")
        self.is_recording = True
        start_time = datetime.datetime.now()

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

        thumbnail, thumbnail_path = self.create_thumbnail(
            start_time,
            self._camera.shared_frames.get_decoded_frame_rgb(shared_frame).copy(),
            objects_in_fov,
            resolution,
        )

        start_time = datetime.datetime.now()

        with self._storage.get_session() as session:
            stmt = (
                insert(Recordings)
                .values(
                    camera_identifier=self._camera.identifier,
                    start_time=start_time,
                    thumbnail_path=thumbnail_path,
                )
                .returning(Recordings.id)
            )
            result = session.execute(stmt).scalars()
            recording_id = result.one()
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

        self._start(recording, shared_frame, objects_in_fov, resolution)
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
        resolution,
    ):
        """Start the recorder."""

    def stop(self, recording: Recording | None) -> None:
        """Stop recording."""
        self._logger.info("Stopping recorder")
        if recording is None:
            self._logger.error("No active recording to stop")
            return

        end_time = datetime.datetime.now()
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
            self._config[CONFIG_RECORDER][CONFIG_LOOKBACK],
            self._storage.get_session,
        )
        fragments = [
            Fragment(file.path, file.meta["m3u8"]["EXTINF"])
            for file in files
            if file.meta.get("m3u8", False).get("EXTINF", False)
        ]
        event_clip = self._camera.fragmenter.concatenate_fragments(fragments)
        if event_clip:
            shutil.move(
                event_clip,
                recording.path,
            )
            self._logger.debug(f"Moved event clip to {recording.path}")
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


class FailedCameraRecorder(RecorderBase):
    """Failed camera recorder.

    Provides access to the recordings for failed cameras.
    """


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


def _recording_file_dict(recording: Recordings) -> RecordingDict:
    """Return a dict with recording file information."""
    return {
        "id": recording.id,
        "camera_identifier": recording.camera_identifier,
        "start_time": recording.start_time,
        "start_timestamp": recording.start_time.timestamp(),
        "end_time": recording.end_time,
        "end_timestamp": recording.end_time.timestamp(),
        "date": recording.start_time.date().isoformat(),
        "trigger_type": recording.trigger_type,
        "trigger_id": recording.trigger_id,
        "thumbnail_path": recording.thumbnail_path,
    }
