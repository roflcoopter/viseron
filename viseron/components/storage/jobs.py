"""Cleanup jobs for removing orphaned files and database records."""
from __future__ import annotations

import datetime
import logging
import multiprocessing as mp
import os
import threading
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import setproctitle
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import and_, delete, exists, func, select

from viseron.components.storage.const import (
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
from viseron.types import SnapshotDomain
from viseron.watchdog.process_watchdog import RestartableProcess
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components.storage import Storage
    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)

BATCH_SIZE = 100


class BaseCleanupJob(ABC):
    """Base class for cleanup jobs."""

    def __init__(
        self, vis: Viseron, storage: Storage, interval_trigger: IntervalTrigger
    ) -> None:
        self._vis = vis
        self._storage = storage
        self._interval_trigger = interval_trigger

        self._last_log_time = 0.0
        self.kill_event = mp.Event()
        self.run_lock = threading.Lock()
        self.running = False

    def _get_cameras(self) -> dict[str, AbstractCamera] | None:
        """Get list of registered camera identifiers."""
        try:
            return self._vis.get_registered_identifiers(CAMERA_DOMAIN)
        except DomainNotRegisteredError:
            return None

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the cleanup job."""

    @property
    def interval_trigger(self) -> IntervalTrigger:
        """Return the trigger interval for the cleanup job."""
        return self._interval_trigger

    @abstractmethod
    def _run(self) -> None:
        """Run the cleanup job."""

    def _wrapped_run(self):
        setproctitle.setproctitle(f"viseron_{self.name}")
        self._storage.engine.dispose(close=False)
        self._run()

    def run(self) -> None:
        """Run the cleanup job using multiprocessing."""
        with self.run_lock:
            if self.running:
                return
            self.running = True

        process = RestartableProcess(
            name=self.name, target=self._wrapped_run, daemon=True, register=False
        )
        process.start()
        process.join()

        with self.run_lock:
            self.running = False

    def log_progress(self, message: str):
        """Log progress of the cleanup job.

        Throttled to only run every 5s so that it doesn't spam the logs.
        """
        now = time.time()
        if now - self._last_log_time > 5:
            LOGGER.debug(message)
            self._last_log_time = now


class BaseTableCleanupJob(BaseCleanupJob):
    """Base class for database table cleanup jobs that use batch processing."""

    def batch_delete_orphaned(self, session, table, path_column):
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
            if self.kill_event.is_set():
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
            result = session.execute(delete(table).where(table.id.in_(batch_ids)))
            session.commit()
            total_deleted += result.rowcount
            self.log_progress(f"{self.name} deleted {result.rowcount} records in batch")
            time.sleep(1)

        LOGGER.debug(
            "%s deleted %d total records, took %s",
            self.name,
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

    def _run(self) -> None:
        """Run the job."""
        now = time.time()
        LOGGER.debug("Running %s", self.name)
        deleted_count = 0
        cameras = self._get_cameras()
        if not cameras:
            return

        paths = []
        for camera in cameras.values():
            paths += self._storage.get_event_clips_path(camera, all_tiers=True)
            paths += self._storage.get_segments_path(camera, all_tiers=True)
            paths += self._storage.get_thumbnails_path(camera, all_tiers=True)

            for domain in SnapshotDomain:
                paths += self._storage.get_snapshots_path(
                    camera, domain, all_tiers=True
                )

        total_files_processed = 0
        with self._storage.get_session() as session:
            for path in paths:
                if self.kill_event.is_set():
                    break
                LOGGER.debug("%s checking %s", self.name, path)
                for root, _, files in os.walk(path):
                    if self.kill_event.is_set():
                        break

                    files_processed = 0
                    for file in files:
                        if self.kill_event.is_set():
                            break

                        total_files_processed += 1
                        files_processed += 1
                        if file in self._storage.ignored_files:
                            continue
                        file_path = os.path.join(root, file)
                        file_exists = session.execute(
                            select(Files).where(Files.path == file_path)
                        ).first()
                        if not file_exists and os.path.exists(file_path):
                            os.remove(file_path)
                            LOGGER.debug("%s deleted %s", self.name, file_path)
                            deleted_count += 1
                        self.log_progress(
                            f"{self.name} processed {files_processed}/{len(files)} "
                            f"files in {root}",
                        )
                        if total_files_processed % 100 == 0:
                            time.sleep(1)
                    LOGGER.debug(
                        f"{self.name} processed {files_processed}/{len(files)} "
                        f"files in {root}",
                    )

        LOGGER.debug(
            "%s deleted %d/%d processed files, took %s",
            self.name,
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

    def _run(self) -> None:
        """Run the job."""
        now = time.time()
        LOGGER.debug("Running %s", self.name)
        total_deleted = 0
        last_id = 0
        total_files_processed = 0

        with self._storage.get_session() as session:
            count = session.execute(
                select(
                    func.count(),  # pylint: disable=not-callable
                ).select_from(Files)
            ).scalar()

            while True:
                if self.kill_event.is_set():
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
                    result = session.execute(
                        delete(Files).where(Files.id.in_(to_delete))
                    )
                    session.commit()
                    total_deleted += result.rowcount
                    LOGGER.debug(
                        "%s deleted %d rows in batch", self.name, result.rowcount
                    )
                total_files_processed += len(files)
                self.log_progress(
                    f"{self.name} processed {total_files_processed}/{count} files"
                )

        LOGGER.debug(
            "%s deleted %d total database records for non-existent files, took %s",
            self.name,
            total_deleted,
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

    def _run(self) -> None:
        """Run the job."""
        now = time.time()
        LOGGER.debug("Running %s", self.name)
        deleted_count = 0
        processed_count = 0
        cameras = self._get_cameras()
        if not cameras:
            return

        paths = []
        for camera in cameras.values():
            paths += self._storage.get_event_clips_path(camera, all_tiers=True)
            paths += self._storage.get_segments_path(camera, all_tiers=True)
            paths += self._storage.get_thumbnails_path(camera, all_tiers=True)

            for domain in SnapshotDomain:
                paths += self._storage.get_snapshots_path(
                    camera, domain, all_tiers=True
                )

        for path in paths:
            time.sleep(1)
            for root, dirs, files in os.walk(path, topdown=False):
                processed_count += 1
                self.log_progress(f"{self.name} processed {processed_count} folders")
                if root == path:
                    continue
                if not dirs and not files:
                    LOGGER.debug("Deleting folder %s", root)
                    os.rmdir(root)
                    deleted_count += 1

        LOGGER.debug(
            "%s deleted %d empty folders, took %s",
            self.name,
            deleted_count,
            time.time() - now,
        )


class OrphanedThumbnailsCleanup(BaseCleanupJob):
    """Cleanup job that removes thumbnail files with no database records."""

    @property
    def name(self) -> str:
        """Return job name."""
        return CleanupJobNames.ORPHANED_THUMBNAILS.value

    def _run(self) -> None:
        """Run the job."""
        now = time.time()
        LOGGER.debug("Running %s", self.name)
        deleted_count = 0
        total_files_processed = 0

        cameras = self._get_cameras()
        if not cameras:
            return

        paths = []
        for camera in cameras.values():
            paths += self._storage.get_thumbnails_path(camera, all_tiers=True)

        with self._storage.get_session() as session:
            for thumbnails_path in paths:
                files_processed = 0
                if not os.path.exists(thumbnails_path):
                    continue

                files_to_check: list[str] = []
                for root, _, files in os.walk(thumbnails_path):
                    files_to_check.extend(
                        os.path.join(root, f)
                        for f in files
                        if f not in self._storage.ignored_files
                    )

                # Process files in batches
                for i in range(0, len(files_to_check), BATCH_SIZE):
                    if self.kill_event.is_set():
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

                    self.log_progress(
                        f"{self.name} processed "
                        f"{files_processed}/{len(files_to_check)} "
                        f"files in {thumbnails_path}"
                    )
                    time.sleep(1)
                LOGGER.debug(
                    f"{self.name} processed "
                    f"{files_processed}/{len(files_to_check)} "
                    f"files in {thumbnails_path}"
                )

        LOGGER.debug(
            "%s deleted %d/%d orphaned thumbnails, took %s",
            self.name,
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

    def _run(self) -> None:
        """Run the job."""
        now = time.time()
        LOGGER.debug("Running %s", self.name)
        deleted_count = 0
        total_files_processed = 0

        cameras = self._get_cameras()
        if not cameras:
            return

        paths = []
        for camera in cameras.values():
            paths += self._storage.get_event_clips_path(camera, all_tiers=True)

        with self._storage.get_session() as session:
            for event_clips_path in paths:
                files_processed = 0
                if not os.path.exists(event_clips_path):
                    continue

                # Collect all files first
                files_to_check: list[str] = []
                for root, _, files in os.walk(event_clips_path):
                    files_to_check.extend(
                        os.path.join(root, f)
                        for f in files
                        if f not in self._storage.ignored_files
                    )

                # Process files in batches
                for i in range(0, len(files_to_check), BATCH_SIZE):
                    if self.kill_event.is_set():
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

                    self.log_progress(
                        f"{self.name} processed "
                        f"{files_processed}/{len(files_to_check)} "
                        f"files in {event_clips_path}"
                    )
                    time.sleep(1)
                LOGGER.debug(
                    f"{self.name} processed "
                    f"{files_processed}/{len(files_to_check)} "
                    f"files in {event_clips_path}"
                )

        LOGGER.debug(
            "%s deleted %d/%d orphaned clips, took %s",
            self.name,
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

    def _run(self) -> None:
        """Run the job."""
        now = time.time()
        LOGGER.debug("Running %s", self.name)
        total_deleted = 0
        total_processed = 0

        with self._storage.get_session() as session:
            count = session.execute(
                select(func.count())  # pylint: disable=not-callable
                .select_from(Recordings)
                .where(Recordings.end_time.is_not(None))
            ).scalar()

            if not count:
                return

            last_id = 0
            while True:
                if self.kill_event.is_set():
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
                    if self.kill_event.is_set():
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
                    result = session.execute(
                        delete(Recordings).where(Recordings.id.in_(to_delete))
                    )
                    session.commit()
                    total_deleted += result.rowcount

                total_processed += len(batch)
                self.log_progress(
                    f"{self.name} processed {total_processed}/{count} recordings"
                )
                time.sleep(1)

        LOGGER.debug(
            "%s deleted %d/%d orphaned recordings, took %s",
            self.name,
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

    def _run(self) -> None:
        """Run the job."""
        LOGGER.debug("Running %s", self.name)
        with self._storage.get_session() as session:
            self.batch_delete_orphaned(
                session, PostProcessorResults, PostProcessorResults.snapshot_path
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

    def _run(self) -> None:
        """Run the job."""
        LOGGER.debug("Running %s", self.name)
        with self._storage.get_session() as session:
            self.batch_delete_orphaned(session, Objects, Objects.snapshot_path)


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

    def _run(self) -> None:
        """Run the job."""
        LOGGER.debug("Running %s", self.name)
        with self._storage.get_session() as session:
            self.batch_delete_orphaned(session, Motion, Motion.snapshot_path)


class OldEventsCleanup(BaseCleanupJob):
    """Cleanup job that removes old events from the database.

    Deletes records from the Events table that are older than a specified
    number of days.
    """

    @property
    def name(self) -> str:
        """Return job name."""
        return CleanupJobNames.OLD_EVENTS.value

    def _run(self) -> None:
        """Run the job."""
        now = time.time()
        LOGGER.debug("Running %s", self.name)
        with self._storage.get_session() as session:
            stmt = delete(Events).where(
                Events.created_at < utcnow() - datetime.timedelta(days=7)
            )
            result = session.execute(stmt)
            session.commit()
            LOGGER.debug(
                "%s deleted %d old events, took %s",
                self.name,
                result.rowcount,
                time.time() - now,
            )


class CleanupManager:
    """Manager class that handles scheduling and running of cleanup jobs.

    Initializes all cleanup jobs and manages their execution through a background
    scheduler. Provides functionality to start and stop the cleanup process for
    both filesystem and database maintenance tasks.
    """

    def __init__(self, vis: Viseron, storage: Storage):
        self._vis = vis
        self.jobs: list[BaseCleanupJob] = [
            OrphanedFilesCleanup(vis, storage, CronTrigger(hour=0, jitter=3600)),
            OrphanedDatabaseFilesCleanup(
                vis, storage, CronTrigger(hour=0, jitter=3600)
            ),
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

    def start(self):
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

    def stop(self):
        """Stop the cleanup scheduler."""
        LOGGER.debug("Stopping cleanup jobs")
        for job in self.jobs:
            LOGGER.debug("Sending kill event to %s", job.name)
            job.kill_event.set()
