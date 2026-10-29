"""Cleanup jobs for removing orphaned files and database records."""

from __future__ import annotations

import datetime
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import setproctitle
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import and_, delete, exists, func, select
from sqlalchemy.orm import sessionmaker

from viseron.components.storage.const import (
    ENGINE,
    TIER_CATEGORY_RECORDER,
    TIER_SUBCATEGORY_SEGMENTS,
    CleanupJobNames,
)
from viseron.components.storage.models import (
    Events,
    Files,
    Motion,
    Objects,
    PostProcessorResults,
    Recordings,
)
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.exceptions import DomainNotRegisteredError
from viseron.helpers import utcnow
from viseron.helpers.child_process_context import (
    CHILD_PROCESS_START_METHOD,
    get_child_process_context,
)
from viseron.helpers.logs import SensitiveInformationFilter, enable_child_logging
from viseron.viseron_types import SnapshotDomain
from viseron.watchdog.process_watchdog import RestartableProcess
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from multiprocessing.synchronize import Event

    from apscheduler.triggers.interval import IntervalTrigger
    from sqlalchemy import CursorResult
    from sqlalchemy.orm import Session

    from viseron import Viseron
    from viseron.components.storage import Storage
    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)

LOG_THROTTLE_SECONDS = 5

BATCH_SIZE = 100


@dataclass(frozen=True)
class CleanupJobConfig:
    """Everything a cleanup job child process needs, as plain picklable data."""

    name: str
    paths: list[str]
    ignored_files: frozenset[str]
    sensitive_strings: tuple[str, ...]
    log_level: int


class CleanupJobRunner:
    """State of a cleanup job running inside the child process."""

    def __init__(self, config: CleanupJobConfig, kill_event: Event) -> None:
        self.name = config.name
        self.paths = config.paths
        self.ignored_files = config.ignored_files
        self.kill_event = kill_event
        self._session_maker = sessionmaker(bind=ENGINE)
        self._last_log_time = 0.0

    def get_session(self) -> Session:
        """Get a new sqlalchemy session."""
        return self._session_maker()

    def log_progress(self, message: str) -> None:
        """Log progress of the cleanup job.

        Throttled to only run every 5s so that it doesn't spam the logs.
        """
        now = time.time()
        if now - self._last_log_time > LOG_THROTTLE_SECONDS:
            LOGGER.debug(message)
            self._last_log_time = now


def run_cleanup_job(
    job: type[BaseCleanupJob], config: CleanupJobConfig, kill_event: Event
) -> None:
    """Entrypoint of the cleanup job child process."""
    setproctitle.setproctitle(f"viseron_{config.name}")
    enable_child_logging(config.sensitive_strings, config.log_level)
    job.work(CleanupJobRunner(config, kill_event))


class BaseCleanupJob(ABC):
    """Base class for cleanup jobs.

    The work of a job runs in a child process created with the forkserver start method
    to reduce memory usage. Anything the work needs from the running Viseron instance
    is resolved into a CleanupJobConfig before the child process is started.
    """

    def __init__(
        self, vis: Viseron, storage: Storage, interval_trigger: IntervalTrigger
    ) -> None:
        self._vis = vis
        self._storage = storage
        self._interval_trigger = interval_trigger

        self.kill_event = get_child_process_context().Event()
        self.run_lock = threading.Lock()
        self.running = False

    def _get_cameras(self) -> dict[str, AbstractCamera] | None:
        """Get list of registered camera identifiers."""
        try:
            return self._vis.get_registered_identifiers(CAMERA_DOMAIN)
        except DomainNotRegisteredError:
            return None

    def _get_all_paths(self) -> list[str]:
        """Return the storage paths of all cameras, across all tiers."""
        cameras = self._get_cameras() or {}
        paths = []
        for camera in cameras.values():
            paths += self._storage.get_event_clips_path(camera, all_tiers=True)
            paths += self._storage.get_segments_path(camera, all_tiers=True)
            paths += self._storage.get_thumbnails_path(camera, all_tiers=True)
            if timelapse_path := self._storage.get_timelapse_path(
                camera, all_tiers=True
            ):
                paths += timelapse_path

            for domain in SnapshotDomain:
                paths += self._storage.get_snapshots_path(
                    camera, domain, all_tiers=True
                )
        return paths

    def _get_paths(self) -> list[str]:
        """Return the storage paths the job processes."""
        return []

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the cleanup job."""

    @property
    def interval_trigger(self) -> IntervalTrigger:
        """Return the trigger interval for the cleanup job."""
        return self._interval_trigger

    @staticmethod
    @abstractmethod
    def work(runner: CleanupJobRunner) -> None:
        """Run the cleanup job inside the child process."""

    def run(self) -> None:
        """Run the cleanup job in a child process."""
        with self.run_lock:
            if self.running:
                return
            self.running = True

        process_config = CleanupJobConfig(
            name=self.name,
            paths=self._get_paths(),
            ignored_files=frozenset(self._storage.ignored_files),
            sensitive_strings=tuple(SensitiveInformationFilter.sensitive_strings),
            log_level=logging.getLogger().level,
        )
        process = RestartableProcess(
            name=self.name,
            target=run_cleanup_job,
            args=(type(self), process_config, self.kill_event),
            daemon=True,
            register=False,
            context=CHILD_PROCESS_START_METHOD,
            child_logger_names=(LOGGER.name,),
        )
        process.start()
        process.join()
        process.stop()

        with self.run_lock:
            self.running = False


class BaseTableCleanupJob(BaseCleanupJob):
    """Base class for database table cleanup jobs that use batch processing."""

    @staticmethod
    def batch_delete_orphaned(
        runner: CleanupJobRunner,
        session: Session,
        table: type[PostProcessorResults | Motion | Objects],
        path_column: Any,
    ) -> None:
        """Delete orphaned records in batches using cursor-based pagination.

        Args:
            session: Database session
            table: SQLAlchemy table to clean up
            path_column: Column containing the file path to check against Files table
        """
        total_deleted = 0
        last_id = 0
        now = time.time()

        # Calculate cutoff time for 5 minutes ago
        cutoff_time = utcnow() - datetime.timedelta(minutes=5)

        while True:
            if runner.kill_event.is_set():
                break

            # Get next batch of records that need checking
            batch = session.execute(
                select(table.id, path_column)
                .where(
                    and_(
                        table.id > last_id,
                        ~exists().where(Files.path == path_column),
                        table.created_at
                        < cutoff_time,  # Only consider records older than 5 minutes
                    )
                )
                .order_by(table.id)
                .limit(BATCH_SIZE)
            ).all()

            if not batch:
                break

            # Update cursor
            last_id = batch[-1][0]

            # Get IDs to delete
            batch_ids = [row[0] for row in batch]

            # Delete the batch
            result = cast(  # https://github.com/sqlalchemy/sqlalchemy/issues/12813
                "CursorResult[Any]",
                session.execute(delete(table).where(table.id.in_(batch_ids))),
            )
            session.commit()
            total_deleted += result.rowcount
            runner.log_progress(
                f"{runner.name} deleted {result.rowcount} records in batch"
            )
            time.sleep(1)

        LOGGER.debug(
            "%s deleted %d total records, took %s",
            runner.name,
            total_deleted,
            time.time() - now,
        )


class OrphanedFilesCleanup(BaseCleanupJob):
    """Cleanup job that removes files with no corresponding database records.

    Walks through recordings, segments and snapshots directories to find and delete
    any files that don't have a matching record in the Files table.
    """

    @property
    def name(self) -> str:
        """Return job name."""
        return CleanupJobNames.ORPHANED_FILES.value

    def _get_paths(self) -> list[str]:
        """Return the storage paths the job processes."""
        return self._get_all_paths()

    @staticmethod
    def work(runner: CleanupJobRunner) -> None:
        """Run the job."""
        now = time.time()
        LOGGER.debug("Running %s", runner.name)
        deleted_count = 0
        if not runner.paths:
            return

        total_files_processed = 0
        with runner.get_session() as session:
            for path in runner.paths:
                if runner.kill_event.is_set():
                    break
                LOGGER.debug("%s checking %s", runner.name, path)
                for root, _, files in os.walk(path):
                    if runner.kill_event.is_set():
                        break

                    files_processed = 0
                    for file in files:
                        if runner.kill_event.is_set():
                            break

                        total_files_processed += 1
                        files_processed += 1
                        if file in runner.ignored_files:
                            continue
                        file_path = os.path.join(root, file)
                        file_exists = session.execute(
                            select(Files).where(Files.path == file_path)
                        ).first()
                        if not file_exists and os.path.exists(file_path):
                            os.remove(file_path)
                            LOGGER.debug("%s deleted %s", runner.name, file_path)
                            deleted_count += 1
                        runner.log_progress(
                            f"{runner.name} processed {files_processed}/{len(files)} "
                            f"files in {root}",
                        )
                        if total_files_processed % 100 == 0:
                            time.sleep(1)
                    LOGGER.debug(
                        f"{runner.name} processed {files_processed}/{len(files)} "
                        f"files in {root}",
                    )

        LOGGER.debug(
            "%s deleted %d/%d processed files, took %s",
            runner.name,
            deleted_count,
            total_files_processed,
            time.time() - now,
        )


class OrphanedDatabaseFilesCleanup(BaseCleanupJob):
    """Cleanup job that removes rows from Files with no corresponding files on disk."""

    @property
    def name(self) -> str:
        """Return job name."""
        return CleanupJobNames.ORPHANED_DB_FILES.value

    @staticmethod
    def work(runner: CleanupJobRunner) -> None:
        """Run the job."""
        now = time.time()
        LOGGER.debug("Running %s", runner.name)
        total_deleted = 0
        last_id = 0
        total_files_processed = 0

        with runner.get_session() as session:
            count = session.execute(
                select(
                    func.count(),
                ).select_from(Files)
            ).scalar()

            while True:
                if runner.kill_event.is_set():
                    break

                # Get next batch of files to check
                time.sleep(1)
                files = session.execute(
                    select(Files.id, Files.path)
                    .where(Files.id > last_id)
                    .order_by(Files.id)
                    .limit(BATCH_SIZE)
                ).all()

                if not files:
                    break

                # Update cursor
                last_id = files[-1][0]

                # Find records where files don't exist
                to_delete = [
                    file_id
                    for file_id, file_path in files
                    if not os.path.exists(file_path)
                ]

                if to_delete:
                    result = cast(
                        "CursorResult[Any]",
                        session.execute(delete(Files).where(Files.id.in_(to_delete))),
                    )
                    session.commit()
                    total_deleted += result.rowcount
                    LOGGER.debug(
                        "%s deleted %d rows in batch", runner.name, result.rowcount
                    )
                total_files_processed += len(files)
                runner.log_progress(
                    f"{runner.name} processed {total_files_processed}/{count} files"
                )

        LOGGER.debug(
            "%s deleted %d total database records for non-existent files, took %s",
            runner.name,
            total_deleted,
            time.time() - now,
        )


class ZeroSizeFilesCleanup(BaseCleanupJob):
    """Cleanup job that handles zero-size files in the database.

    For any Files in the database with zero size, the job will attempt to update the
    size. If the size on disk is zero the file is removed.
    """

    @property
    def name(self) -> str:
        """Return job name."""
        return CleanupJobNames.ZERO_SIZE_FILES.value

    @staticmethod
    def work(runner: CleanupJobRunner) -> None:
        """Run the job."""
        now = time.time()
        LOGGER.debug("Running %s", runner.name)
        processed = 0
        updated = 0
        deleted = 0
        last_id = 0

        # Only consider files older than 5 minutes
        cutoff_time = utcnow() - datetime.timedelta(minutes=5)

        with runner.get_session() as session:
            while True:
                if runner.kill_event.is_set():
                    break

                batch = (
                    session.execute(
                        select(Files)
                        .where(
                            and_(
                                Files.id > last_id,
                                Files.size == 0,
                                Files.created_at < cutoff_time,
                            )
                        )
                        .order_by(Files.id)
                        .limit(BATCH_SIZE)
                    )
                    .scalars()
                    .all()
                )

                if not batch:
                    break

                last_id = batch[-1].id

                to_delete_ids: list[int] = []
                for file_row in batch:
                    if runner.kill_event.is_set():
                        break
                    processed += 1
                    path = file_row.path
                    try:
                        stat_size = os.path.getsize(path)
                    except OSError:
                        stat_size = 0

                    if stat_size > 0:
                        file_row.size = stat_size
                        updated += 1
                    else:
                        if os.path.exists(path):
                            os.remove(path)
                        to_delete_ids.append(file_row.id)
                        deleted += 1

                if to_delete_ids:
                    session.execute(delete(Files).where(Files.id.in_(to_delete_ids)))
                session.commit()
                time.sleep(0.5)

        LOGGER.debug(
            "%s processed %d files, updated %d sizes, deleted %d records, took %s",
            runner.name,
            processed,
            updated,
            deleted,
            time.time() - now,
        )


class EmptyFoldersCleanup(BaseCleanupJob):
    """Cleanup job that removes empty directories from the storage locations.

    Walks through all storage paths (recordings, segments, thumbnails, snapshots)
    and removes any empty directories encountered. Uses a bottom-up traversal to
    ensure nested empty directories are handled properly.
    """

    @property
    def name(self) -> str:
        """Return job name."""
        return CleanupJobNames.EMPTY_FOLDERS.value

    def _get_paths(self) -> list[str]:
        """Return the storage paths the job processes."""
        return self._get_all_paths()

    @staticmethod
    def work(runner: CleanupJobRunner) -> None:
        """Run the job."""
        now = time.time()
        LOGGER.debug("Running %s", runner.name)
        deleted_count = 0
        processed_count = 0
        if not runner.paths:
            return

        for path in runner.paths:
            time.sleep(1)
            for root, dirs, files in os.walk(path, topdown=False):
                processed_count += 1
                runner.log_progress(
                    f"{runner.name} processed {processed_count} folders"
                )
                if root == path:
                    continue
                if not dirs and not files:
                    LOGGER.debug("Deleting folder %s", root)
                    os.rmdir(root)
                    deleted_count += 1

        LOGGER.debug(
            "%s deleted %d empty folders, took %s",
            runner.name,
            deleted_count,
            time.time() - now,
        )


class OrphanedThumbnailsCleanup(BaseCleanupJob):
    """Cleanup job that removes thumbnail files with no database records."""

    @property
    def name(self) -> str:
        """Return job name."""
        return CleanupJobNames.ORPHANED_THUMBNAILS.value

    def _get_paths(self) -> list[str]:
        """Return the storage paths the job processes."""
        cameras = self._get_cameras() or {}
        paths = []
        for camera in cameras.values():
            paths += self._storage.get_thumbnails_path(camera, all_tiers=True)
        return paths

    @staticmethod
    def work(runner: CleanupJobRunner) -> None:
        """Run the job."""
        now = time.time()
        LOGGER.debug("Running %s", runner.name)
        deleted_count = 0
        total_files_processed = 0

        if not runner.paths:
            return

        with runner.get_session() as session:
            for thumbnails_path in runner.paths:
                files_processed = 0
                if not os.path.exists(thumbnails_path):
                    continue

                files_to_check: list[str] = []
                for root, _, files in os.walk(thumbnails_path):
                    files_to_check.extend(
                        os.path.join(root, f)
                        for f in files
                        if f not in runner.ignored_files
                    )

                # Process files in batches
                for i in range(0, len(files_to_check), BATCH_SIZE):
                    if runner.kill_event.is_set():
                        break

                    batch = files_to_check[i : i + BATCH_SIZE]
                    existing_thumbnails = {
                        row[0]
                        for row in session.execute(
                            select(Recordings.thumbnail_path).where(
                                Recordings.thumbnail_path.in_(batch)
                            )
                        ).all()
                    }

                    # Delete files that don't exist in database
                    for file_path in batch:
                        if file_path not in existing_thumbnails and os.path.exists(
                            file_path
                        ):
                            os.remove(file_path)
                            deleted_count += 1
                        total_files_processed += 1
                        files_processed += 1

                    runner.log_progress(
                        f"{runner.name} processed "
                        f"{files_processed}/{len(files_to_check)} "
                        f"files in {thumbnails_path}"
                    )
                    time.sleep(1)
                LOGGER.debug(
                    f"{runner.name} processed "
                    f"{files_processed}/{len(files_to_check)} "
                    f"files in {thumbnails_path}"
                )

        LOGGER.debug(
            "%s deleted %d/%d orphaned thumbnails, took %s",
            runner.name,
            deleted_count,
            total_files_processed,
            time.time() - now,
        )


class OrphanedEventClipsCleanup(BaseCleanupJob):
    """Cleanup job that removes clip files with no corresponding database records."""

    @property
    def name(self) -> str:
        """Return job name."""
        return CleanupJobNames.ORPHANED_EVENT_CLIPS.value

    def _get_paths(self) -> list[str]:
        """Return the storage paths the job processes."""
        cameras = self._get_cameras() or {}
        paths = []
        for camera in cameras.values():
            paths += self._storage.get_event_clips_path(camera, all_tiers=True)
        return paths

    @staticmethod
    def work(runner: CleanupJobRunner) -> None:
        """Run the job."""
        now = time.time()
        LOGGER.debug("Running %s", runner.name)
        deleted_count = 0
        total_files_processed = 0

        if not runner.paths:
            return

        with runner.get_session() as session:
            for event_clips_path in runner.paths:
                files_processed = 0
                if not os.path.exists(event_clips_path):
                    continue

                # Collect all files first
                files_to_check: list[str] = []
                for root, _, files in os.walk(event_clips_path):
                    files_to_check.extend(
                        os.path.join(root, f)
                        for f in files
                        if f not in runner.ignored_files
                    )

                # Process files in batches
                for i in range(0, len(files_to_check), BATCH_SIZE):
                    if runner.kill_event.is_set():
                        break

                    batch = files_to_check[i : i + BATCH_SIZE]
                    existing_clips = {
                        row[0]
                        for row in session.execute(
                            select(Recordings.clip_path).where(
                                Recordings.clip_path.in_(batch)
                            )
                        ).all()
                    }

                    # Delete files that don't exist in database
                    for file_path in batch:
                        if file_path not in existing_clips and os.path.exists(
                            file_path
                        ):
                            os.remove(file_path)
                            deleted_count += 1
                        total_files_processed += 1
                        files_processed += 1

                    runner.log_progress(
                        f"{runner.name} processed "
                        f"{files_processed}/{len(files_to_check)} "
                        f"files in {event_clips_path}"
                    )
                    time.sleep(1)
                LOGGER.debug(
                    f"{runner.name} processed "
                    f"{files_processed}/{len(files_to_check)} "
                    f"files in {event_clips_path}"
                )

        LOGGER.debug(
            "%s deleted %d/%d orphaned clips, took %s",
            runner.name,
            deleted_count,
            total_files_processed,
            time.time() - now,
        )


class OrphanedRecordingsCleanup(BaseCleanupJob):
    """Cleanup job that removes orphaned recording entries from the database."""

    @property
    def name(self) -> str:
        """Return job name."""
        return CleanupJobNames.ORPHANED_RECORDINGS.value

    @staticmethod
    def work(runner: CleanupJobRunner) -> None:
        """Run the job."""
        now = time.time()
        LOGGER.debug("Running %s", runner.name)
        total_deleted = 0
        total_processed = 0

        with runner.get_session() as session:
            count = session.execute(
                select(func.count())
                .select_from(Recordings)
                .where(Recordings.end_time.is_not(None))
            ).scalar()

            if not count:
                return

            last_id = 0
            while True:
                if runner.kill_event.is_set():
                    break

                # Get next batch of recordings
                batch = session.execute(
                    select(Recordings)
                    .where(
                        and_(Recordings.id > last_id, Recordings.end_time.is_not(None))
                    )
                    .order_by(Recordings.id)
                    .limit(BATCH_SIZE)
                ).all()

                if not batch:
                    break

                # Update cursor
                last_id = batch[-1][0].id

                # Find orphaned recordings
                to_delete = []
                for recording in batch:
                    if runner.kill_event.is_set():
                        break
                    has_segments = session.execute(
                        select(1)
                        .select_from(Files)
                        .where(
                            and_(
                                Files.category == TIER_CATEGORY_RECORDER,
                                Files.subcategory == TIER_SUBCATEGORY_SEGMENTS,
                                Files.camera_identifier
                                == recording[0].camera_identifier,
                                Files.orig_ctime.between(
                                    recording[0].start_time, recording[0].end_time
                                ),
                            )
                        )
                        .limit(1)
                    ).first()
                    time.sleep(0.1)

                    if not has_segments:
                        to_delete.append(recording[0].id)

                if to_delete:
                    result = cast(
                        "CursorResult[Any]",
                        session.execute(
                            delete(Recordings).where(Recordings.id.in_(to_delete))
                        ),
                    )
                    session.commit()
                    total_deleted += result.rowcount

                total_processed += len(batch)
                runner.log_progress(
                    f"{runner.name} processed {total_processed}/{count} recordings"
                )
                time.sleep(1)

        LOGGER.debug(
            "%s deleted %d/%d orphaned recordings, took %s",
            runner.name,
            total_deleted,
            total_processed,
            time.time() - now,
        )


class OrphanedPostProcessorResultsCleanup(BaseTableCleanupJob):
    """Cleanup job that removes orphaned post-processor results from the database.

    Deletes records from the PostProcessorResults table where the referenced
    snapshot file no longer exists in the Files table, ensuring that results
    without associated files are removed.
    """

    @property
    def name(self) -> str:
        """Return job name."""
        return CleanupJobNames.ORPHANED_POSTPROCESSOR_RESULTS.value

    @staticmethod
    def work(runner: CleanupJobRunner) -> None:
        """Run the job."""
        LOGGER.debug("Running %s", runner.name)
        with runner.get_session() as session:
            BaseTableCleanupJob.batch_delete_orphaned(
                runner,
                session,
                PostProcessorResults,
                PostProcessorResults.snapshot_path,
            )


class OrphanedObjectsCleanup(BaseTableCleanupJob):
    """Cleanup job that removes orphaned object detection records from the database.

    Deletes records from the Objects table where the referenced snapshot file
    no longer exists in the Files table, ensuring that object detections
    without associated files are removed.
    """

    @property
    def name(self) -> str:
        """Return job name."""
        return CleanupJobNames.ORPHANED_OBJECTS.value

    @staticmethod
    def work(runner: CleanupJobRunner) -> None:
        """Run the job."""
        LOGGER.debug("Running %s", runner.name)
        with runner.get_session() as session:
            BaseTableCleanupJob.batch_delete_orphaned(
                runner, session, Objects, Objects.snapshot_path
            )


class OrphanedMotionCleanup(BaseTableCleanupJob):
    """Cleanup job that removes orphaned motion detection records from the database.

    Deletes records from the Motion table where the referenced snapshot file
    no longer exists in the Files table, ensuring that motion detections
    without associated files are removed.
    """

    @property
    def name(self) -> str:
        """Return job name."""
        return CleanupJobNames.ORPHANED_MOTION.value

    @staticmethod
    def work(runner: CleanupJobRunner) -> None:
        """Run the job."""
        LOGGER.debug("Running %s", runner.name)
        with runner.get_session() as session:
            BaseTableCleanupJob.batch_delete_orphaned(
                runner, session, Motion, Motion.snapshot_path
            )


class OldEventsCleanup(BaseCleanupJob):
    """Cleanup job that removes old events from the database.

    Deletes records from the Events table that are older than a specified
    number of days.
    """

    @property
    def name(self) -> str:
        """Return job name."""
        return CleanupJobNames.OLD_EVENTS.value

    @staticmethod
    def work(runner: CleanupJobRunner) -> None:
        """Run the job."""
        now = time.time()
        LOGGER.debug("Running %s", runner.name)
        with runner.get_session() as session:
            stmt = delete(Events).where(
                Events.created_at < utcnow() - datetime.timedelta(days=7)
            )
            result = cast("CursorResult[Any]", session.execute(stmt))
            session.commit()
            LOGGER.debug(
                "%s deleted %d old events, took %s",
                runner.name,
                result.rowcount,
                time.time() - now,
            )


class CleanupManager:
    """Manager class that handles scheduling and running of cleanup jobs.

    Initializes all cleanup jobs and manages their execution through a background
    scheduler. Provides functionality to start and stop the cleanup process for
    both filesystem and database maintenance tasks.
    """

    def __init__(self, vis: Viseron, storage: Storage) -> None:
        self._vis = vis
        self.jobs: list[BaseCleanupJob] = [
            OrphanedFilesCleanup(vis, storage, CronTrigger(hour=0, jitter=3600)),
            OrphanedDatabaseFilesCleanup(
                vis, storage, CronTrigger(hour=0, jitter=3600)
            ),
            ZeroSizeFilesCleanup(vis, storage, CronTrigger(hour=0, jitter=3600)),
            EmptyFoldersCleanup(vis, storage, CronTrigger(hour=0, jitter=3600)),
            OrphanedThumbnailsCleanup(vis, storage, CronTrigger(hour=0, jitter=3600)),
            OrphanedEventClipsCleanup(vis, storage, CronTrigger(hour=0, jitter=3600)),
            OrphanedRecordingsCleanup(vis, storage, CronTrigger(hour=0, jitter=3600)),
            OrphanedPostProcessorResultsCleanup(
                vis, storage, CronTrigger(hour=0, jitter=3600)
            ),
            OrphanedObjectsCleanup(vis, storage, CronTrigger(hour=0, jitter=3600)),
            OrphanedMotionCleanup(vis, storage, CronTrigger(hour=0, jitter=3600)),
            OldEventsCleanup(vis, storage, CronTrigger(hour=0, jitter=3600)),
        ]
        vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, self.stop)

    def run_job(self, job_name: CleanupJobNames) -> None:
        """Run a specific cleanup job."""
        for job in self.jobs:
            if job.name == job_name.value:
                with job.run_lock:
                    if job.running:
                        return
                LOGGER.debug("Running cleanup job %s", job.name)
                RestartableThread(
                    name=f"run_job_{job.name}",
                    target=job.run,
                    register=False,
                    daemon=True,
                ).start()
                return

    def start(self) -> None:
        """Start the cleanup scheduler."""
        for job in self.jobs:
            self._vis.background_scheduler.add_job(
                job.run,
                trigger=job.interval_trigger,
                name=job.name,
                id=job.name,
                max_instances=1,
                coalesce=True,
                replace_existing=True,
            )

    def stop(self) -> None:
        """Stop the cleanup scheduler."""
        LOGGER.debug("Stopping cleanup jobs")
        for job in self.jobs:
            LOGGER.debug("Sending kill event to %s", job.name)
            job.kill_event.set()
