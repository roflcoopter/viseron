"""Tier handler."""
from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timedelta
from queue import Queue
from threading import Timer
from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy import Result, delete, insert, select, update
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
from viseron.components.storage.models import Files
from viseron.components.storage.queries import (
    files_to_move_query,
    recordings_to_move_query,
)
from viseron.components.storage.util import (
    calculate_age,
    calculate_bytes,
    files_to_move_overlap,
)
from viseron.const import CAMERA_SEGMENT_DURATION, VISERON_SIGNAL_LAST_WRITE
from viseron.domains.camera.const import CONFIG_RECORDER, CONFIG_RETAIN
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.storage import Storage
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
        self._time_of_last_call = datetime.min

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

    def initialize(self):
        """Tier handler specific initialization."""
        self._max_bytes = calculate_bytes(self._tier[CONFIG_MAX_SIZE])
        self._min_bytes = calculate_bytes(self._tier[CONFIG_MIN_SIZE])
        self._max_age = calculate_age(self._tier[CONFIG_MAX_AGE])
        self._min_age = calculate_age(self._tier[CONFIG_MIN_AGE])

    def check_tier(self) -> None:
        """Check if file should be moved to next tier."""
        now = datetime.now()
        time_since_last_call = now - self._time_of_last_call
        if time_since_last_call > self._throttle_period:
            pass
        else:
            return
        self._check_tier()
        self._time_of_last_call = now

    def _check_tier(self) -> None:
        file_ids = None
        with self._storage.get_session() as session:
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
        LOGGER.debug("File modified: %s", event.src_path)

        def _update_size() -> None:
            """Update the size of a file in the database.

            Runs in a Timer to avoid spamming updates on duplicate events.
            """
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

    def _check_tier(self) -> None:
        events_file_ids = None
        continuous_file_ids = None
        with self._storage.get_session() as session:
            events_file_ids = get_recordings_to_move(
                session,
                self._tier_id,
                self._camera.identifier,
                self._events_max_bytes,
                self._events_min_age,
                self._events_min_bytes,
                self._events_max_age,
            )

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

            overlap = files_to_move_overlap(events_file_ids, continuous_file_ids)
            for file in overlap:
                handle_file(
                    session,
                    self._tier,
                    self._next_tier,
                    file.path,
                )

            session.commit()


def handle_file(
    session: Session,
    curr_tier: dict[str, Any],
    next_tier: dict[str, Any] | None,
    path: str,
) -> None:
    """Move file if there is a preceding tier, else delete the file."""
    if next_tier is None:
        delete_file(session, path)
    else:
        move_file(
            session,
            path,
            path.replace(curr_tier[CONFIG_PATH], next_tier[CONFIG_PATH]),
        )


def move_file(session: Session, src: str, dst: str) -> None:
    """Move file from src to dst."""
    LOGGER.debug("Moving file from %s to %s", src, dst)
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
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
    except FileNotFoundError:
        LOGGER.error(f"Failed to delete file {path}")


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
    now = datetime.utcnow()

    min_age_timestamp = (now - min_age).timestamp()
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
    max_bytes: int,
    min_age: timedelta,
    min_bytes: int,
    max_age: timedelta,
) -> Result[Any]:
    """Get id of recordings and segments to move."""
    now = datetime.utcnow()

    min_age_timestamp = (now - min_age).timestamp()
    if max_age:
        max_age_timestamp = (now - max_age).timestamp()
    else:
        max_age_timestamp = 0

    stmt = recordings_to_move_query(
        CAMERA_SEGMENT_DURATION,
        tier_id,
        camera_identifier,
        max_bytes,
        min_age_timestamp,
        min_bytes,
        max_age_timestamp,
    )
    result = session.execute(stmt)
    return result


def force_move_files(
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
            handle_file(session, curr_tier, next_tier, file.path)
        session.commit()
