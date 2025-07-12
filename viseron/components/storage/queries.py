"""Database queries."""
from __future__ import annotations

import datetime
import logging
from collections.abc import Callable

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import coalesce

from viseron.components.storage.const import (
    TIER_CATEGORY_RECORDER,
    TIER_SUBCATEGORY_SEGMENTS,
)
from viseron.components.storage.models import Files, Recordings
from viseron.helpers import utcnow

LOGGER = logging.getLogger(__name__)


def get_recording_fragments(
    recording_id,
    lookback: float,
    get_session: Callable[[], Session],
    now=None,
):
    """Return a list of files for this recording.

    We must sort on orig_ctime and not created_at as the created_at timestamp is
    not accurate for m4s files that are created from the original mp4 file after
    it has been recorded. The orig_ctime is the timestamp of the original mp4 file
    and is therefore accurate.

    Only the latest occurrence of each file is selected using the CTE row_number.
    This is to accommodate for the case where a file has been copied to a succeeding
    tier but has not been deleted from the original tier yet.
    """
    row_number = (
        func.row_number()
        .over(partition_by=Files.filename, order_by=desc(Files.created_at))
        .label("row_number")
    )
    recording_files = (
        select(Files)
        .add_columns(row_number)
        .join(Recordings, Files.camera_identifier == Recordings.camera_identifier)
        .where(Recordings.id == recording_id)
        .where(Files.category == TIER_CATEGORY_RECORDER)
        .where(Files.subcategory == TIER_SUBCATEGORY_SEGMENTS)
        .where(Files.duration.isnot(None))
        .where(
            or_(
                # Fetch all files that start within the recording
                Files.orig_ctime.between(
                    Recordings.start_time - datetime.timedelta(seconds=lookback),
                    coalesce(Recordings.end_time, now if now else utcnow()),
                ),
                # Fetch the first file that starts before the recording but
                # ends during the recording
                and_(
                    Recordings.start_time - datetime.timedelta(seconds=lookback)
                    >= Files.orig_ctime,
                    Recordings.start_time - datetime.timedelta(seconds=lookback)
                    <= Files.orig_ctime
                    + func.make_interval(
                        0,  # years
                        0,  # months
                        0,  # days
                        0,  # hours
                        0,  # minutes
                        0,  # seconds
                        func.round(Files.duration),
                    ),
                ),
            )
        )
        .order_by(Files.orig_ctime.asc())
        .cte("recording_files")
    )
    stmt = (
        select(recording_files)
        .where(recording_files.c.row_number == 1)
        .order_by(recording_files.c.orig_ctime.asc())
    )
    with get_session() as session:
        fragments = session.execute(stmt).all()
    return fragments


def get_time_period_fragments(
    camera_identifiers: list[str],
    start_timestamp: int | float,
    end_timestamp: int | float | None,
    get_session: Callable[[], Session],
    now=None,
):
    """Return a list of files for the requested time period."""
    start = datetime.datetime.fromtimestamp(start_timestamp, tz=datetime.timezone.utc)
    if end_timestamp:
        end = datetime.datetime.fromtimestamp(end_timestamp, tz=datetime.timezone.utc)
    else:
        end = now if now else utcnow()

    row_number = (
        func.row_number()
        .over(partition_by=Files.filename, order_by=desc(Files.created_at))
        .label("row_number")
    )
    files = (
        select(Files)
        .add_columns(row_number)
        .where(Files.camera_identifier.in_(camera_identifiers))
        .where(Files.category == TIER_CATEGORY_RECORDER)
        .where(Files.subcategory == TIER_SUBCATEGORY_SEGMENTS)
        .where(Files.duration.isnot(None))
        .where(
            or_(
                # Fetch all files that start within the recording
                Files.orig_ctime.between(
                    start,
                    end,
                ),
                # Fetch the first file that starts before the recording but
                # ends during the recording
                and_(
                    start >= Files.orig_ctime,
                    start
                    <= Files.orig_ctime
                    + func.make_interval(
                        0,  # years
                        0,  # months
                        0,  # days
                        0,  # hours
                        0,  # minutes
                        0,  # seconds
                        func.round(Files.duration),
                    ),
                ),
            )
        )
        .order_by(Files.orig_ctime.asc())
        .cte("files")
    )
    stmt = (
        select(files).where(files.c.row_number == 1).order_by(files.c.orig_ctime.asc())
    )
    with get_session() as session:
        fragments = session.execute(stmt).all()
    return fragments
