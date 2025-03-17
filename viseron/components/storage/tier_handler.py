"""Tier handler."""
from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Callable
from datetime import datetime, timedelta
from queue import Queue
from threading import Lock, Timer
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import Delete, Result, delete, insert, select, update
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session
from sqlalchemy.sql.dml import ReturningDelete
from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserverVFS

from viseron.components.storage.const import (
    COMPONENT,
    CONFIG_CHECK_INTERVAL,
    CONFIG_CONTINUOUS,
    CONFIG_DAYS,
    CONFIG_EVENTS,
    CONFIG_HOURS,
    CONFIG_MAX_AGE,
    CONFIG_MAX_SIZE,
    CONFIG_MIN_AGE,
    CONFIG_MIN_SIZE,
    CONFIG_MINUTES,
    CONFIG_MOVE_ON_SHUTDOWN,
    CONFIG_PATH,
    CONFIG_POLL,
    CONFIG_SECONDS,
    EVENT_FILE_CREATED,
    EVENT_FILE_DELETED,
    TIER_CATEGORY_RECORDER,
    TIER_SUBCATEGORY_EVENT_CLIPS,
    TIER_SUBCATEGORY_FACE_RECOGNITION,
    TIER_SUBCATEGORY_LICENSE_PLATE_RECOGNITION,
    TIER_SUBCATEGORY_MOTION_DETECTOR,
    TIER_SUBCATEGORY_OBJECT_DETECTOR,
    TIER_SUBCATEGORY_SEGMENTS,
    TIER_SUBCATEGORY_THUMBNAILS,
)
from viseron.components.storage.models import (
    Files,
    FilesMeta,
    Motion,
    MotionContours,
    Objects,
    PostProcessorResults,
    Recordings,
)
from viseron.components.storage.queries import (
    files_to_move_query,
    recordings_to_move_query,
)
from viseron.components.storage.util import (
    EventFileCreated,
    EventFileDeleted,
    calculate_age,
    calculate_bytes,
    files_to_move_overlap,
    get_event_clips_path,
    get_segments_path,
    get_thumbnails_path,
)
from viseron.components.webserver.const import COMPONENT as WEBSERVER_COMPONENT
from viseron.const import (
    CAMERA_SEGMENT_DURATION,
    VISERON_SIGNAL_LAST_WRITE,
    VISERON_SIGNAL_STOPPING,
)
from viseron.domains.camera import FailedCamera
from viseron.domains.camera.const import (
    CONFIG_CONTINUOUS_RECORDING,
    CONFIG_RECORDER,
    CONFIG_RETAIN,
)
from viseron.helpers import utcnow
from viseron.helpers.named_timer import NamedTimer
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.storage import Storage
    from viseron.components.webserver import Webserver
    from viseron.domains.camera import AbstractCamera


class TierHandler(FileSystemEventHandler):
    """Moves files up configured tiers."""

    def __init__(
        self,
        vis: Viseron,
        camera: AbstractCamera,
        tier_id: int,
        category: str,
        subcategory: str,
        tier: dict[str, Any],
        next_tier: dict[str, Any] | None,
    ) -> None:
        self._logger = logging.getLogger(
            f"{__name__}.{camera.identifier}.tier_{tier_id}.{category}.{subcategory}"
        )
        super().__init__()

        self._vis = vis
        self._storage: Storage = vis.data[COMPONENT]
        self._webserver: Webserver = self._vis.data[WEBSERVER_COMPONENT]
        self._camera = camera
        self._tier_id = tier_id
        self._category = category
        self._subcategory = subcategory
        self._tier = tier
        self._next_tier = next_tier

        self.initialize()
        vis.register_signal_handler(VISERON_SIGNAL_LAST_WRITE, self._shutdown)
        vis.register_signal_handler(VISERON_SIGNAL_STOPPING, self._stop_observer)

        self._pending_updates: dict[str, Timer] = {}
        self._event_queue: Queue[FileSystemEvent | None] = Queue()
        self._event_thread = RestartableThread(
            target=self._process_events,
            daemon=True,
            name=f"tier_handler_{camera.identifier}",
            stage=VISERON_SIGNAL_LAST_WRITE,
        )
        self._event_thread.start()

        self._throttle_period = timedelta(
            days=tier[CONFIG_CHECK_INTERVAL].get(CONFIG_DAYS, 0),
            hours=tier[CONFIG_CHECK_INTERVAL].get(CONFIG_HOURS, 0),
            minutes=tier[CONFIG_CHECK_INTERVAL].get(CONFIG_MINUTES, 0),
            seconds=tier[CONFIG_CHECK_INTERVAL].get(CONFIG_SECONDS, 0),
        )
        self._time_of_last_call = utcnow()
        self._check_tier_lock = Lock()

        self._logger.debug("Tier %s monitoring path: %s", tier_id, self._path)
        os.makedirs(self._path, exist_ok=True)
        self._observer = (
            PollingObserverVFS(stat=os.stat, listdir=os.scandir, polling_interval=1)
            if tier[CONFIG_POLL]
            else Observer()
        )
        self._observer.schedule(
            self,
            self._path,
            recursive=True,
        )
        self._observer.start()

    @property
    def tier(self) -> dict[str, Any]:
        """Tier configuration."""
        return self._tier

    @property
    def first_tier(self) -> bool:
        """Return if first tier."""
        return self._tier_id == 0

    @property
    def tier_id(self) -> int:
        """Return tier id."""
        return self._tier_id

    def add_file_handler(self, path: str, pattern: str):
        """Add file handler to webserver."""
        self._logger.debug(f"Adding handler for /files{pattern}")
        add_file_handler(
            self._vis,
            self._webserver,
            path,
            pattern,
            self._camera,
            self._category,
            self._subcategory,
        )

    def initialize(self):
        """Tier handler specific initialization."""
        self._path = os.path.join(
            self._tier[CONFIG_PATH],
            self._category,
            self._subcategory,
            self._camera.identifier,
        )

        self._max_bytes = calculate_bytes(self._tier[CONFIG_MAX_SIZE])
        self._min_bytes = calculate_bytes(self._tier[CONFIG_MIN_SIZE])
        self._max_age = calculate_age(self._tier[CONFIG_MAX_AGE])
        self._min_age = calculate_age(self._tier[CONFIG_MIN_AGE])

    def check_tier(self) -> None:
        """Check if file should be moved to next tier."""
        now = utcnow()
        with self._check_tier_lock:
            time_since_last_call = now - self._time_of_last_call
            if time_since_last_call < self._throttle_period:
                return
            self._time_of_last_call = now

        self._check_tier(self._storage.get_session)

    def _check_tier(self, get_session: Callable[[], Session]) -> None:
        file_ids = None
        with get_session() as session:
            file_ids = get_files_to_move(
                session,
                self._category,
                self._subcategory,
                self._tier_id,
                self._camera.identifier,
                self._max_bytes,
                self._min_age,
                self._min_bytes,
                self._max_age,
            ).all()

            if file_ids is not None:
                for file in file_ids:
                    handle_file(
                        get_session,
                        self._storage,
                        self._camera.identifier,
                        self._tier,
                        self._next_tier,
                        file.path,
                        file.tier_path,
                        self._logger,
                    )
            session.commit()

    def _process_events(self) -> None:
        while True:
            event = self._event_queue.get()
            if event is None:
                self._logger.debug("Stopping event handler")
                break
            if isinstance(event, FileDeletedEvent):
                self._on_deleted(event)
            elif isinstance(event, FileCreatedEvent):
                self._on_created(event)
            elif isinstance(event, FileModifiedEvent):
                self._on_modified(event)

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Handle file system events."""
        if os.path.basename(event.src_path) in self._storage.ignored_files:
            return
        self._event_queue.put(event)

    def _on_created(self, event: FileCreatedEvent) -> None:
        """Insert into database when file is created."""
        self._logger.debug("File created: %s", event.src_path)
        file_meta = self._storage.temporary_files_meta.pop(event.src_path, None)
        try:
            with self._storage.get_session() as session:
                stmt = insert(Files).values(
                    tier_id=self._tier_id,
                    tier_path=self._tier[CONFIG_PATH],
                    camera_identifier=self._camera.identifier,
                    category=self._category,
                    subcategory=self._subcategory,
                    path=event.src_path,
                    directory=os.path.dirname(event.src_path),
                    filename=os.path.basename(event.src_path),
                    size=os.path.getsize(event.src_path),
                    orig_ctime=file_meta.orig_ctime if file_meta else utcnow(),
                    duration=file_meta.duration if file_meta else None,
                )
                session.execute(stmt)
                session.commit()
        except IntegrityError:
            self._logger.error(
                "Failed to insert file %s into database, already exists", event.src_path
            )
        else:
            self._vis.dispatch_event(
                EVENT_FILE_CREATED.format(
                    camera_identifier=self._camera.identifier,
                    category=self._category,
                    subcategory=self._subcategory,
                    file_name="*",
                ),
                EventFileCreated(
                    camera_identifier=self._camera.identifier,
                    category=self._category,
                    subcategory=self._subcategory,
                    file_name=os.path.basename(event.src_path),
                    path=event.src_path,
                ),
            )

        self.check_tier()

    def _on_modified(self, event: FileModifiedEvent) -> None:
        """Update database when file is moved."""

        def _update_size() -> None:
            """Update the size of a file in the database.

            Runs in a Timer to avoid spamming updates on duplicate events.
            """
            self._logger.debug("File modified (delayed event): %s", event.src_path)
            self._pending_updates.pop(event.src_path, None)
            try:
                size = os.path.getsize(event.src_path)
            except FileNotFoundError:
                self._logger.debug("File not found: %s", event.src_path)
                return

            with self._storage.get_session() as session:
                stmt = (
                    update(Files).where(Files.path == event.src_path).values(size=size)
                )
                session.execute(stmt)
                session.commit()

            self.check_tier()

        if event.src_path in self._pending_updates:
            self._pending_updates[event.src_path].cancel()
        self._pending_updates[event.src_path] = NamedTimer(
            1,
            _update_size,
            name=f"update_size for {event.src_path}",
            daemon=False,  # We want to wait for the update to finish on shutdown
        )
        self._pending_updates[event.src_path].start()

    def _on_deleted(self, event: FileDeletedEvent) -> None:
        """Remove file from database when it is deleted."""
        self._logger.debug("File deleted: %s", event.src_path)
        with self._storage.get_session() as session:
            stmt = delete(Files).where(Files.path == event.src_path)
            session.execute(stmt)
            session.commit()

        self._vis.dispatch_event(
            EVENT_FILE_DELETED.format(
                camera_identifier=self._camera.identifier,
                category=self._category,
                subcategory=self._subcategory,
                file_name=os.path.basename(event.src_path),
            ),
            EventFileDeleted(
                camera_identifier=self._camera.identifier,
                category=self._category,
                subcategory=self._subcategory,
                file_name=os.path.basename(event.src_path),
                path=event.src_path,
            ),
        )

    def _shutdown(self) -> None:
        """Shutdown the observer and event handler."""
        self._logger.debug("Initiating observer shutdown")
        if self._tier[CONFIG_MOVE_ON_SHUTDOWN]:
            self._logger.debug("Forcing move of files")
            force_move_files(
                self._storage,
                self._storage.get_session,
                self._category,
                self._subcategory,
                self._tier_id,
                self._camera.identifier,
                self._tier,
                self._next_tier,
                self._logger,
            )

    def _stop_observer(self) -> None:
        """Stop the observer."""
        self._logger.debug("Stopping observer")
        for pending_update in self._pending_updates.copy().values():
            pending_update.join()
        self._event_queue.put(None)
        self._event_thread.join()
        self._observer.stop()
        self._observer.join()


class SegmentsTierHandler(TierHandler):
    """Handle the recorder tiers."""

    def initialize(self) -> None:
        """Initialize recorder tier."""
        self._path = get_segments_path(self._tier, self._camera)

        self._continuous_max_bytes = calculate_bytes(
            self._tier[CONFIG_CONTINUOUS][CONFIG_MAX_SIZE]
        )
        self._continuous_min_bytes = calculate_bytes(
            self._tier[CONFIG_CONTINUOUS][CONFIG_MIN_SIZE]
        )
        self._continuous_max_age = calculate_age(
            self._tier[CONFIG_CONTINUOUS][CONFIG_MAX_AGE]
        )
        self._continuous_min_age = calculate_age(
            self._tier[CONFIG_CONTINUOUS][CONFIG_MIN_AGE]
        )
        self._continuous_params = [
            self._continuous_max_bytes,
            self._continuous_min_age,
            self._continuous_min_bytes,
            self._continuous_max_age,
        ]

        self._events_max_bytes = calculate_bytes(
            self._tier[CONFIG_EVENTS][CONFIG_MAX_SIZE]
        )
        self._events_min_bytes = calculate_bytes(
            self._tier[CONFIG_EVENTS][CONFIG_MIN_SIZE]
        )
        self._events_min_age = calculate_age(self._tier[CONFIG_EVENTS][CONFIG_MIN_AGE])

        if self.first_tier and self._camera.config.get(CONFIG_RECORDER, {}).get(
            CONFIG_RETAIN, None
        ):
            self._logger.warning(
                f"Camera {self._camera.identifier} is using 'retain' for 'recorder' "
                "which has been deprecated and will be removed in a future release. "
                "Please use the new 'storage' component with the 'max_age' config "
                "option instead. For now, the value of 'retain' will be used as "
                "'max_age' for the first tier, but this WILL change and might cause "
                "you to lose data."
            )
            self._events_max_age = timedelta(
                days=self._camera.config[CONFIG_RECORDER][CONFIG_RETAIN]
            )
        else:
            self._events_max_age = calculate_age(
                self._tier[CONFIG_EVENTS][CONFIG_MAX_AGE]
            )
        self._events_params = [
            self._events_max_bytes,
            self._events_max_age,
            self._events_min_bytes,
            self._events_min_age,
        ]

        self._events_enabled = any(self._events_params)
        self._continuous_enabled = (
            any(self._continuous_params)
            and self._camera.config[CONFIG_RECORDER][CONFIG_CONTINUOUS_RECORDING]
        )

        self.add_file_handler(self._path, rf"{self._path}/(.*.m4s$)")
        self.add_file_handler(self._path, rf"{self._path}/(.*.mp4$)")

    @property
    def events_enabled(self) -> bool:
        """Return if events are enabled."""
        return self._events_enabled

    @property
    def continuous_enabled(self) -> bool:
        """Return if continuous is enabled."""
        return self._continuous_enabled

    def _get_events_file_ids(self, session: Session) -> Result[Any] | list:
        if self._events_enabled:
            return get_recordings_to_move(
                session,
                self._tier_id,
                self._camera.identifier,
                self._events_max_bytes,
                self._events_min_age,
                self._events_min_bytes,
                self._events_max_age,
            )
        return []

    def _get_continuous_file_ids(self, session: Session) -> Result[Any] | list:
        if self._continuous_enabled:
            return get_files_to_move(
                session,
                self._category,
                self._subcategory,
                self._tier_id,
                self._camera.identifier,
                self._continuous_max_bytes,
                self._continuous_min_age,
                self._continuous_min_bytes,
                self._continuous_max_age,
            )
        return []

    def _check_tier(self, get_session: Callable[[], Session]) -> None:
        with get_session() as session:
            # Convert to list since we iterate over it twice and the Result closes
            # after the first loop
            events_file_ids = list(self._get_events_file_ids(session))
            continuous_file_ids = self._get_continuous_file_ids(session)

            # A file can be in multiple recordings, so we need to keep track of which
            # files we have already processed using processed_paths
            processed_paths = []
            events_next_tier = None
            continuous_next_tier = None
            if self._events_enabled and not self._continuous_enabled:
                events_next_tier = find_next_tier_segments(
                    self._storage, self._tier_id, self._camera, "events"
                )
                for file in events_file_ids:
                    if file.path in processed_paths:
                        continue
                    force_delete = bool(file.recording_id is None)
                    handle_file(
                        get_session,
                        self._storage,
                        self._camera.identifier,
                        self._tier,
                        events_next_tier.tier if events_next_tier else None,
                        file.path,
                        file.tier_path,
                        self._logger,
                        force_delete,
                    )
                    processed_paths.append(file.path)
            elif self._continuous_enabled and not self._events_enabled:
                continuous_next_tier = find_next_tier_segments(
                    self._storage, self._tier_id, self._camera, "continuous"
                )
                for file in continuous_file_ids:
                    handle_file(
                        get_session,
                        self._storage,
                        self._camera.identifier,
                        self._tier,
                        continuous_next_tier.tier if continuous_next_tier else None,
                        file.path,
                        file.tier_path,
                        self._logger,
                    )
            else:
                overlap = files_to_move_overlap(events_file_ids, continuous_file_ids)
                events_next_tier = find_next_tier_segments(
                    self._storage, self._tier_id, self._camera, "events"
                )
                continuous_next_tier = find_next_tier_segments(
                    self._storage, self._tier_id, self._camera, "continuous"
                )
                for file in overlap:
                    if file.path in processed_paths:
                        continue

                    force_delete = False
                    next_tier = None
                    # If the file is not part of a recording, and no succeeding tiers
                    # store continuous recordings we can delete the file
                    if file.recording_id is None and continuous_next_tier is None:
                        force_delete = True
                    # If no succeeding tier stores either events or continuous
                    # recordings, we can delete the file
                    elif events_next_tier is None and continuous_next_tier is None:
                        force_delete = True
                    elif events_next_tier and continuous_next_tier is None:
                        next_tier = events_next_tier
                    elif continuous_next_tier and events_next_tier is None:
                        next_tier = continuous_next_tier
                    elif events_next_tier and continuous_next_tier:
                        # Find the lowest tier_id for the two next tiers
                        next_tier = (
                            events_next_tier
                            if events_next_tier.tier_id < continuous_next_tier.tier_id
                            else continuous_next_tier
                        )

                    handle_file(
                        get_session,
                        self._storage,
                        self._camera.identifier,
                        self._tier,
                        next_tier.tier if next_tier else None,
                        file.path,
                        file.tier_path,
                        self._logger,
                        force_delete=force_delete,
                    )
                    processed_paths.append(file.path)

            recording_ids: list[int] = []
            for recording in events_file_ids:
                if (
                    recording.recording_id
                    and recording.recording_id not in recording_ids
                ):
                    recording_ids.append(recording.recording_id)

            # Signal to the thumbnail tier that the recording has been moved
            if recording_ids:
                self._logger.debug(
                    "Handle thumbnails for recordings: %s", recording_ids
                )
                for recording_id in recording_ids:
                    thumbnail_tier_handler: ThumbnailTierHandler = (
                        self._storage.camera_tier_handlers[self._camera.identifier][
                            self._category
                        ][self._tier_id][TIER_SUBCATEGORY_THUMBNAILS]
                    )
                    thumbnail_tier_handler.move_thumbnail(
                        recording_id,
                        events_next_tier.tier if events_next_tier else None,
                    )

            # Signal to the recordings tier that the recording has been moved
            if recording_ids:
                self._logger.debug(
                    "Handle event clip for recordings: %s", recording_ids
                )
                for recording_id in recording_ids:
                    recordings_tier_handler: EventClipTierHandler = (
                        self._storage.camera_tier_handlers[self._camera.identifier][
                            self._category
                        ][self._tier_id][TIER_SUBCATEGORY_EVENT_CLIPS]
                    )
                    recordings_tier_handler.move_event_clip(
                        recording_id,
                        events_next_tier.tier if events_next_tier else None,
                    )

            # Delete recordings from Recordings table if this is the last tier
            if recording_ids and events_next_tier is None:
                self._logger.debug("Deleting recordings: %s", recording_ids)
                with get_session() as _session:
                    stmt = delete(Recordings).where(Recordings.id.in_(recording_ids))
                    _session.execute(stmt)
                    _session.commit()

            session.commit()


class SnapshotTierHandler(TierHandler):
    """Handle the snapshot tiers."""

    def initialize(self):
        """Initialize snapshot tier."""
        super().initialize()
        self.add_file_handler(self._path, rf"{self._path}/(.*.jpg$)")

    def _on_deleted(self, event: FileDeletedEvent) -> None:
        stmt: Delete | ReturningDelete[tuple[int]]
        if self._subcategory == TIER_SUBCATEGORY_MOTION_DETECTOR:
            with self._storage.get_session() as session:
                stmt = (
                    delete(Motion)
                    .where(Motion.snapshot_path == event.src_path)
                    .returning(Motion.id)
                )
                result = session.execute(stmt)
                motion_ids = [row[0] for row in result]

                if motion_ids:
                    stmt2 = delete(MotionContours).where(
                        MotionContours.motion_id.in_(motion_ids)
                    )
                    session.execute(stmt2)

                session.commit()

        elif self._subcategory == TIER_SUBCATEGORY_OBJECT_DETECTOR:
            with self._storage.get_session() as session:
                stmt = delete(Objects).where(Objects.snapshot_path == event.src_path)
                session.execute(stmt)
                session.commit()

        elif self._subcategory in [
            TIER_SUBCATEGORY_FACE_RECOGNITION,
            TIER_SUBCATEGORY_LICENSE_PLATE_RECOGNITION,
        ]:
            with self._storage.get_session() as session:
                stmt = delete(PostProcessorResults).where(
                    PostProcessorResults.snapshot_path == event.src_path
                )
                session.execute(stmt)
                session.commit()

        super()._on_deleted(event)


class ThumbnailTierHandler(TierHandler):
    """Handle thumbnails."""

    def initialize(self):
        """Initialize thumbnail tier."""
        self._path = get_thumbnails_path(self._tier, self._camera)
        self.add_file_handler(self._path, rf"{self._path}/(.*.jpg$)")
        self._storage.ignore_file("latest_thumbnail.jpg")

    def check_tier(self) -> None:
        """Do nothing, as we don't want to move thumbnails."""

    def _on_created(self, event: FileCreatedEvent) -> None:
        try:
            with self._storage.get_session() as session:
                stmt = (
                    update(Recordings)
                    .where(
                        Recordings.id == os.path.basename(event.src_path).split(".")[0]
                    )
                    .values(thumbnail_path=event.src_path)
                )
                session.execute(stmt)
                session.commit()
        except Exception as error:  # pylint: disable=broad-except
            self._logger.error(
                "Failed to update thumbnail path for recording with path: "
                f"{event.src_path}: {error}"
            )
        super()._on_created(event)

    def move_thumbnail(
        self, recording_id: int, next_tier: dict[str, Any] | None
    ) -> None:
        """Move thumbnail to next tier."""
        with self._storage.get_session() as session:
            sel = select(Recordings).where(Recordings.id == recording_id)
            try:
                recording = session.execute(sel).scalar_one()
            except NoResultFound as err:
                self._logger.error(
                    "Failed to move thumbnail for recording with id %s: %s",
                    recording_id,
                    err,
                )
                return

            handle_file(
                self._storage.get_session,
                self._storage,
                self._camera.identifier,
                self._tier,
                next_tier,
                recording.thumbnail_path,
                self._tier[CONFIG_PATH],
                self._logger,
            )
            session.commit()


class EventClipTierHandler(TierHandler):
    """Handle event clips created by create_event_clip."""

    def initialize(self):
        """Initialize event clips tier."""
        self._path = get_event_clips_path(self._tier, self._camera)
        self.add_file_handler(
            self._path, rf"{self._path}/(.*.{self._camera.identifier}$)"
        )

    def check_tier(self) -> None:
        """Do nothing, as we move event clips manually."""

    def _update_clip_path(self, event: FileCreatedEvent) -> None:
        try:
            with self._storage.get_session() as session:
                stmt = (
                    update(Recordings)
                    .where(Recordings.camera_identifier == self._camera.identifier)
                    .where(
                        Recordings.clip_path.like(
                            f"%{event.src_path.split('/')[-2]}/"
                            f"{os.path.basename(event.src_path)}"
                        )
                    )
                    .values(clip_path=event.src_path)
                )
                session.execute(stmt)
                session.commit()
        except Exception as error:  # pylint: disable=broad-except
            self._logger.error(
                "Failed to update clip path for recording with path: "
                f"{event.src_path}: {error}"
            )

    def _on_created(self, event: FileCreatedEvent) -> None:
        if not self.first_tier:
            self._update_clip_path(event)
        super()._on_created(event)

    def move_event_clip(
        self, recording_id: int, next_tier: dict[str, Any] | None
    ) -> None:
        """Move event clip to next tier."""
        with self._storage.get_session() as session:
            sel = (
                select(Recordings)
                .where(Recordings.id == recording_id)
                .where(Recordings.clip_path.is_not(None))
            )
            recording = session.execute(sel).scalar()
            if recording is None:
                return

            handle_file(
                self._storage.get_session,
                self._storage,
                self._camera.identifier,
                self._tier,
                next_tier,
                recording.clip_path,
                self._tier[CONFIG_PATH],
                self._logger,
            )
            session.commit()


def find_next_tier_segments(
    storage: Storage,
    tier_id: int,
    camera: AbstractCamera,
    file_type: Literal["events", "continuous"],
) -> SegmentsTierHandler | None:
    """Find the next tier for segments."""
    next_tier = None
    for tier in storage.camera_tier_handlers[camera.identifier][TIER_CATEGORY_RECORDER][
        tier_id + 1 :
    ]:
        segments_tier_handler: SegmentsTierHandler = tier[TIER_SUBCATEGORY_SEGMENTS]
        if segments_tier_handler.events_enabled and file_type == "events":
            next_tier = segments_tier_handler
            break
        if segments_tier_handler.continuous_enabled and file_type == "continuous":
            next_tier = segments_tier_handler
            break
    return next_tier


def handle_file(
    get_session: Callable[..., Session],
    storage: Storage,
    camera_identifier: str,
    curr_tier: dict[str, Any],
    next_tier: dict[str, Any] | None,
    path: str,
    tier_path: str,
    logger: logging.Logger,
    force_delete: bool = False,
) -> None:
    """Move file if there is a succeeding tier, else delete the file."""
    if path in storage.camera_requested_files_count[camera_identifier].filenames:
        logger.debug("File %s is recently requested, skipping", path)
        return

    if force_delete or next_tier is None:
        delete_file(get_session, path, logger)
    else:
        new_path = path.replace(tier_path, next_tier[CONFIG_PATH], 1)
        if new_path == path:
            logger.warning(
                "Failed to move file %s to next tier, new path is the same as old. "
                "Viseron tries to mitigate this, but it can happen if you recently "
                "changed the tier paths or a previous move failed.",
                path,
            )
        else:
            move_file(
                storage,
                get_session,
                path,
                new_path,
                logger,
            )

    # Delete the file from the database if tier_path is not the same as
    # curr_tier[CONFIG_PATH]. This is an indication that the tier configuration
    # has changed and since the old path is not monitored, the delete signal
    # will not be received by Viseron
    if tier_path != curr_tier[CONFIG_PATH]:
        logger.debug(
            "Deleting file %s from database since tier paths are different. "
            "file tier_path: %s, current tier_path: %s",
            path,
            tier_path,
            curr_tier[CONFIG_PATH],
        )
        with get_session() as session:
            stmt = delete(Files).where(Files.path == path)
            session.execute(stmt)
            session.commit()


def move_file(
    storage: Storage,
    get_session: Callable[..., Session],
    src: str,
    dst: str,
    logger: logging.Logger,
) -> None:
    """Move file from src to dst.

    To avoid race conditions where a file is referenced at the same time as it is being
    moved, causing a 404 in the browser, we copy the file to the new location and then
    delete the old one.
    """
    logger.debug("Moving file from %s to %s", src, dst)
    try:
        with get_session() as session:
            sel = select(Files).where(Files.path == src)
            res = session.execute(sel).scalar_one()
            storage.temporary_files_meta[dst] = FilesMeta(
                orig_ctime=res.orig_ctime, duration=res.duration
            )
    except NoResultFound as error:
        logger.debug(f"Failed to find metadata for {src}: {error}")
        with get_session() as session:
            stmt = delete(Files).where(Files.path == src)
            session.execute(stmt)
            session.commit()
        try:
            os.remove(src)
        except FileNotFoundError as _error:
            logger.debug(f"Failed to delete file {src}: {_error}")
        return

    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(src, dst)
        os.remove(src)
    except FileNotFoundError as error:
        logger.debug(f"Failed to move file {src} to {dst}: {error}")
        with get_session() as session:
            stmt = delete(Files).where(Files.path == src)
            session.execute(stmt)
            session.commit()


def delete_file(
    get_session: Callable[..., Session],
    path: str,
    logger: logging.Logger,
) -> None:
    """Delete file."""
    logger.debug("Deleting file %s", path)
    with get_session() as session:
        stmt = delete(Files).where(Files.path == path)
        session.execute(stmt)
        session.commit()

    try:
        os.remove(path)
    except FileNotFoundError as error:
        logger.debug(f"Failed to delete file {path}: {error}")


def get_files_to_move(
    session: Session,
    category: str,
    subcategory: str,
    tier_id: int,
    camera_identifier: str,
    max_bytes: int,
    min_age: timedelta,
    min_bytes: int,
    max_age: timedelta,
) -> Result[Any]:
    """Get id of files to move."""
    now = utcnow()

    # If min_age is not set, we want to ignore files that are less than 5 seconds old
    # This is to avoid moving files that are still being written to
    if min_age:
        min_age_timestamp = (now - min_age).timestamp()
    else:
        min_age_timestamp = (now - timedelta(seconds=5)).timestamp()

    if max_age:
        max_age_timestamp = (now - max_age).timestamp()
    else:
        max_age_timestamp = 0

    stmt = files_to_move_query(
        category,
        subcategory,
        tier_id,
        camera_identifier,
        max_bytes,
        min_age_timestamp,
        min_bytes,
        max_age_timestamp,
    )
    result = session.execute(stmt)
    return result


def get_recordings_to_move(
    session: Session,
    tier_id: int,
    camera_identifier: str,
    max_bytes: int,
    min_age: timedelta,
    min_bytes: int,
    max_age: timedelta,
    now: datetime | None = None,
) -> Result[Any]:
    """Get id of recordings and segments to move."""
    if now is None:
        now = utcnow()

    min_age_timestamp = (now - min_age).timestamp()
    if max_age:
        max_age_timestamp = (now - max_age).timestamp()
    else:
        max_age_timestamp = 0

    # We want to ignore files that are less than 5 times the
    # segment duration old. This is to improve HLS streaming
    file_min_age = (now - timedelta(seconds=CAMERA_SEGMENT_DURATION * 5)).timestamp()

    stmt = recordings_to_move_query(
        CAMERA_SEGMENT_DURATION,
        tier_id,
        camera_identifier,
        max_bytes,
        min_age_timestamp,
        min_bytes,
        max_age_timestamp,
        file_min_age,
    )
    result = session.execute(stmt)
    return result


def force_move_files(
    storage: Storage,
    get_session: Callable[..., Session],
    category: str,
    subcategory: str,
    tier_id: int,
    camera_identifier: str,
    curr_tier: dict[str, Any],
    next_tier: dict[str, Any] | None,
    logger: logging.Logger,
) -> None:
    """Get and move/delete all files in tier."""
    with get_session(expire_on_commit=False) as session:
        stmt = (
            select(Files.path, Files.tier_path)
            .where(Files.camera_identifier == camera_identifier)
            .where(Files.tier_id == tier_id)
            .where(Files.category == category)
            .where(Files.subcategory == subcategory)
        )
        result = session.execute(stmt).all()
        for file in result:
            handle_file(
                get_session,
                storage,
                camera_identifier,
                curr_tier,
                next_tier,
                file[0],
                file[1],
                logger,
            )
        session.commit()


def add_file_handler(
    vis: Viseron,
    webserver: Webserver,
    path: str,
    pattern: str,
    camera: AbstractCamera | FailedCamera,
    category: str,
    subcategory: str,
) -> None:
    """Add file handler to webserver."""
    # We have to import this here to avoid circular imports
    # pylint: disable-next=import-outside-toplevel
    from viseron.components.webserver.tiered_file_handler import TieredFileHandler

    webserver.application.add_handlers(
        r".*",
        [
            (
                (rf"/files{pattern}"),
                TieredFileHandler,
                {
                    "path": path,
                    "vis": vis,
                    "camera_identifier": camera.identifier,
                    "failed": bool(isinstance(camera, FailedCamera)),
                    "category": category,
                    "subcategory": subcategory,
                },
            )
        ],
    )
