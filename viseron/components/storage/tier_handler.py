"""Tier handler."""
from __future__ import annotations

import logging
import os
import shutil
from datetime import timedelta
from queue import Queue
from threading import Lock, Timer
from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy import Result, delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
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
    CONFIG_CONTINUOUS,
    CONFIG_EVENTS,
    CONFIG_MAX_AGE,
    CONFIG_MAX_SIZE,
    CONFIG_MIN_AGE,
    CONFIG_MIN_SIZE,
    CONFIG_MOVE_ON_SHUTDOWN,
    CONFIG_PATH,
    CONFIG_POLL,
    MOVE_FILES_THROTTLE_SECONDS,
)
from viseron.components.storage.models import Files, FilesMeta, Recordings
from viseron.components.storage.queries import (
    files_to_move_query,
    recordings_to_move_query,
)
from viseron.components.storage.util import (
    calculate_age,
    calculate_bytes,
    files_to_move_overlap,
)
from viseron.components.webserver.const import COMPONENT as WEBSERVER_COMPONENT
from viseron.const import CAMERA_SEGMENT_DURATION, VISERON_SIGNAL_LAST_WRITE
from viseron.domains.camera.const import CONFIG_LOOKBACK, CONFIG_RECORDER, CONFIG_RETAIN
from viseron.helpers import utcnow
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.storage import Storage
    from viseron.components.webserver import Webserver
    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)


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
        self._path = os.path.join(
            tier[CONFIG_PATH], category, subcategory, camera.identifier
        )

        self.initialize()
        vis.register_signal_handler(VISERON_SIGNAL_LAST_WRITE, self._shutdown)

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
            seconds=MOVE_FILES_THROTTLE_SECONDS,
        )
        self._time_of_last_call = utcnow()
        self._check_tier_lock = Lock()

        LOGGER.debug("Tier %s monitoring path: %s", tier_id, self._path)
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

    def add_file_handler(self, path: str, pattern: str):
        """Add file handler to webserver."""
        # We have to import this here to avoid circular imports
        # pylint: disable-next=import-outside-toplevel
        from viseron.components.webserver.tiered_file_handler import TieredFileHandler

        LOGGER.error(f"Adding handler for /files{pattern}")
        self._webserver.application.add_handlers(
            r".*",
            [
                (
                    (rf"/files{pattern}"),
                    TieredFileHandler,
                    {
                        "path": path,
                        "vis": self._vis,
                        "camera_identifier": self._camera.identifier,
                        "failed": False,
                        "category": self._category,
                        "subcategory": self._subcategory,
                    },
                )
            ],
        )

    def initialize(self):
        """Tier handler specific initialization."""
        self._max_bytes = calculate_bytes(self._tier[CONFIG_MAX_SIZE])
        self._min_bytes = calculate_bytes(self._tier[CONFIG_MIN_SIZE])
        self._max_age = calculate_age(self._tier[CONFIG_MAX_AGE])
        self._min_age = calculate_age(self._tier[CONFIG_MIN_AGE])

    def check_tier(self) -> None:
        """Check if file should be moved to next tier."""
        now = utcnow()
        with self._check_tier_lock:
            time_since_last_call = now - self._time_of_last_call
            if time_since_last_call > self._throttle_period:
                self._time_of_last_call = now
            else:
                return
        self._check_tier(self._storage.get_session)
        self._time_of_last_call = now

    def _check_tier(self, get_session: Callable[[], Session]) -> None:
        file_ids = None
        with get_session() as session:
            file_ids = get_files_to_move(
                session,
                self._category,
                self._tier_id,
                self._camera.identifier,
                self._max_bytes,
                self._min_age,
                self._min_bytes,
                self._max_age,
            )

            if file_ids is not None:
                for file in file_ids:
                    handle_file(
                        session,
                        self._storage,
                        self._camera.identifier,
                        self._tier,
                        self._next_tier,
                        file.path,
                    )
            session.commit()

    def _process_events(self) -> None:
        while True:
            event = self._event_queue.get()
            if event is None:
                LOGGER.debug("Stopping event handler")
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
        LOGGER.debug("File created: %s", event.src_path)
        with self._storage.get_session() as session:
            stmt = insert(Files).values(
                tier_id=self._tier_id,
                camera_identifier=self._camera.identifier,
                category=self._category,
                path=event.src_path,
                directory=os.path.dirname(event.src_path),
                filename=os.path.basename(event.src_path),
                size=os.path.getsize(event.src_path),
            )
            session.execute(stmt)
            session.commit()

        self.check_tier()

    def _on_modified(self, event: FileModifiedEvent) -> None:
        """Update database when file is moved."""

        def _update_size() -> None:
            """Update the size of a file in the database.

            Runs in a Timer to avoid spamming updates on duplicate events.
            """
            LOGGER.debug("File modified (delayed event): %s", event.src_path)
            self._pending_updates.pop(event.src_path, None)
            try:
                size = os.path.getsize(event.src_path)
            except FileNotFoundError:
                LOGGER.debug("File not found: %s", event.src_path)
                return

            with self._storage.get_session() as session:
                with session.begin():
                    stmt = (
                        update(Files)
                        .where(Files.path == event.src_path)
                        .values(size=size)
                    )
                    session.execute(stmt)

            self.check_tier()

        if event.src_path in self._pending_updates:
            self._pending_updates[event.src_path].cancel()
        self._pending_updates[event.src_path] = Timer(1, _update_size)
        self._pending_updates[event.src_path].start()

    def _on_deleted(self, event: FileDeletedEvent) -> None:
        """Remove file from database when it is deleted."""
        LOGGER.debug("File deleted: %s", event.src_path)
        with self._storage.get_session() as session:
            with session.begin():
                stmt = delete(Files).where(Files.path == event.src_path)
                session.execute(stmt)

    def _shutdown(self) -> None:
        """Shutdown the observer and event handler."""
        LOGGER.debug("Stopping observer")
        if self._tier[CONFIG_MOVE_ON_SHUTDOWN]:
            LOGGER.debug("Forcing move of files")
            force_move_files(
                self._storage,
                self._storage.get_session,
                self._category,
                self._tier_id,
                self._camera.identifier,
                self._tier,
                self._next_tier,
            )
        for pending_update in self._pending_updates.copy().values():
            pending_update.join()
        self._event_queue.put(None)
        self._event_thread.join()
        self._observer.stop()
        self._observer.join()


class RecorderTierHandler(TierHandler):
    """Handle the recorder tiers."""

    def initialize(self) -> None:
        """Initialize recorder tier."""
        self._path = os.path.join(
            self._tier[CONFIG_PATH],
            self._subcategory,
            self._camera.identifier,
        )

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

        if self._tier_id == 0 and self._camera.config.get(CONFIG_RECORDER, {}).get(
            CONFIG_RETAIN, None
        ):
            LOGGER.warning(
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

        thumbnail_path = os.path.join(
            self._tier[CONFIG_PATH],
            "thumbnails",
            self._camera.identifier,
        )

        self.add_file_handler(self._path, rf"{self._path}/(.*.m4s$)")
        self.add_file_handler(self._path, rf"{self._path}/(.*.mp4$)")
        self.add_file_handler(thumbnail_path, rf"{thumbnail_path}/(.*.jpg$)")

    def _check_tier(self, get_session: Callable[[], Session]) -> None:
        events_enabled = False
        continuous_enabled = False
        events_file_ids: Result[Any] | list = []
        continuous_file_ids: Result[Any] | list = []
        with get_session() as session:
            if any(self._events_params):
                events_enabled = True
                events_file_ids = get_recordings_to_move(
                    session,
                    self._tier_id,
                    self._camera.identifier,
                    self._camera.config[CONFIG_RECORDER][CONFIG_LOOKBACK],
                    self._events_max_bytes,
                    self._events_min_age,
                    self._events_min_bytes,
                    self._events_max_age,
                )

            if any(self._continuous_params):
                continuous_enabled = True
                continuous_file_ids = get_files_to_move(
                    session,
                    self._category,
                    self._tier_id,
                    self._camera.identifier,
                    self._continuous_max_bytes,
                    self._continuous_min_age,
                    self._continuous_min_bytes,
                    self._continuous_max_age,
                )

            if events_enabled and not continuous_enabled:
                for file in events_file_ids:
                    handle_file(
                        session,
                        self._storage,
                        self._camera.identifier,
                        self._tier,
                        self._next_tier,
                        file.path,
                    )
            if continuous_enabled and not events_enabled:
                for file in continuous_file_ids:
                    handle_file(
                        session,
                        self._storage,
                        self._camera.identifier,
                        self._tier,
                        self._next_tier,
                        file.path,
                    )
            else:
                overlap = files_to_move_overlap(events_file_ids, continuous_file_ids)
                for file in overlap:
                    handle_file(
                        session,
                        self._storage,
                        self._camera.identifier,
                        self._tier,
                        self._next_tier,
                        file.path,
                    )

            # Delete recordings from Recordings table
            recording_ids: list[int] = []
            for recording in events_file_ids:
                if recording.recording_id not in recording_ids:
                    recording_ids.append(recording.recording_id)

            if recording_ids:
                stmt = delete(Recordings).where(Recordings.id.in_(recording_ids))
                session.execute(stmt)

            session.commit()


def handle_file(
    session: Session,
    storage: Storage,
    camera_identifier: str,
    curr_tier: dict[str, Any],
    next_tier: dict[str, Any] | None,
    path: str,
) -> None:
    """Move file if there is a succeeding tier, else delete the file."""
    if path in storage.camera_requested_files_count[camera_identifier].filenames:
        LOGGER.debug("File %s is recently requested, skipping", path)
        return

    if next_tier is None:
        delete_file(session, path)
    else:
        move_file(
            session,
            path,
            path.replace(curr_tier[CONFIG_PATH], next_tier[CONFIG_PATH], 1),
        )


def move_file(session: Session, src: str, dst: str) -> None:
    """Move file from src to dst.

    To avoid race conditions where a file is referenced at the same time as it is being
    moved, causing a 404 in the browser, we copy the file to the new location and then
    delete the old one.
    """
    LOGGER.debug("Moving file from %s to %s", src, dst)
    sel = select(FilesMeta).where(FilesMeta.path == src)
    res = session.execute(sel).scalar_one()
    try:
        ins = insert(FilesMeta).values(
            path=dst, meta=res.meta, orig_ctime=res.orig_ctime
        )
        session.execute(ins)
    except IntegrityError:
        LOGGER.error(f"Failed to insert metadata for {dst}", exc_info=True)

    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(src, dst)
        os.remove(src)
    except FileNotFoundError as error:
        LOGGER.error(f"Failed to move file {src} to {dst}: {error}")
        stmt = delete(Files).where(Files.path == src)
        session.execute(stmt)


def delete_file(session: Session, path: str) -> None:
    """Delete file."""
    LOGGER.debug("Deleting file %s", path)
    stmt = delete(Files).where(Files.path == path)
    session.execute(stmt)

    try:
        os.remove(path)
    except FileNotFoundError as error:
        LOGGER.error(f"Failed to delete file {path}: {error}")


def get_files_to_move(
    session: Session,
    category: str,
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
    lookback: int,
    max_bytes: int,
    min_age: timedelta,
    min_bytes: int,
    max_age: timedelta,
) -> Result[Any]:
    """Get id of recordings and segments to move."""
    now = utcnow()

    min_age_timestamp = (now - min_age).timestamp()
    if max_age:
        max_age_timestamp = (now - max_age).timestamp()
    else:
        max_age_timestamp = 0

    stmt = recordings_to_move_query(
        CAMERA_SEGMENT_DURATION,
        tier_id,
        camera_identifier,
        lookback,
        max_bytes,
        min_age_timestamp,
        min_bytes,
        max_age_timestamp,
    )
    result = session.execute(stmt)
    return result


def force_move_files(
    storage: Storage,
    get_session: Callable[..., Session],
    category: str,
    tier_id: int,
    camera_identifier: str,
    curr_tier: dict[str, Any],
    next_tier: dict[str, Any] | None,
) -> None:
    """Get and move/delete all files in tier."""
    with get_session() as session:
        stmt = (
            select(Files)
            .where(Files.category == category)
            .where(Files.tier_id == tier_id)
            .where(Files.camera_identifier == camera_identifier)
        )
        result = session.execute(stmt)
        for file in result:
            handle_file(
                session, storage, camera_identifier, curr_tier, next_tier, file.path
            )
        session.commit()
