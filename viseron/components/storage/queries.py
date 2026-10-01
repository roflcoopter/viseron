"""Database queries."""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

from sqlalchemy import ColumnElement, and_, desc, distinct, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import coalesce

from viseron.components.storage.const import (
    TIER_CATEGORY_RECORDER,
    TIER_CATEGORY_TIMELAPSE,
    TIER_SUBCATEGORY_SEGMENTS,
    TIER_SUBCATEGORY_TIMELAPSE,
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
                # Fetch all files that start between the start and end timestamp
                Files.orig_ctime.between(
                    start,
                    end,
                ),
                # Fetch the first file that starts before the start timestamp but
                # ends during the requested time period
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


@dataclass
class TimelapseFrame:
    """A single timelapse frame."""

    file_key: int
    path: str
    orig_ctime: datetime.datetime


class TimelapseFrames(NamedTuple):
    """Timelapse frames in a time range.

    total is the number of unique frames in the range. step is the bucket size in
    seconds used for downsampling, or None if every frame was returned.
    """

    total: int
    step: float | None
    frames: list[TimelapseFrame]


@dataclass
class TimelapseSummary:
    """Summary of the stored timelapse frames for a camera."""

    count: int
    first: datetime.datetime | None
    last: datetime.datetime | None
    latest_frame: TimelapseFrame | None


def _timelapse_filter(camera_identifiers: list[str]) -> tuple[ColumnElement[bool], ...]:
    return (
        Files.camera_identifier.in_(camera_identifiers),
        Files.category == TIER_CATEGORY_TIMELAPSE,
        Files.subcategory == TIER_SUBCATEGORY_TIMELAPSE,
    )


def get_timelapse_frames(
    camera_identifier: str,
    start_timestamp: float,
    end_timestamp: float,
    max_frames: int,
    get_session: Callable[[], Session],
) -> TimelapseFrames:
    """Return the timelapse frames between start and end, oldest first.

    A frame that exists in multiple tiers while being moved is only returned once,
    from the lowest tier. If there are more than max_frames frames, the span
    between the first and last frame is split into max_frames equally sized buckets
    and the first frame of each bucket is returned.
    """
    in_range = (
        *_timelapse_filter([camera_identifier]),
        Files.orig_ctime.between(
            datetime.datetime.fromtimestamp(start_timestamp, tz=datetime.timezone.utc),
            datetime.datetime.fromtimestamp(end_timestamp, tz=datetime.timezone.utc),
        ),
    )
    with get_session() as session:
        total, first, last = session.execute(
            select(
                func.count(distinct(Files.file_key)),  # pylint: disable=not-callable
                func.min(Files.orig_ctime),
                func.max(Files.orig_ctime),
            ).where(*in_range)
        ).one()
        if not total:
            return TimelapseFrames(total=0, step=None, frames=[])

        unique_frames = (
            select(Files.file_key, Files.path, Files.orig_ctime)
            .where(*in_range)
            .distinct(Files.file_key)
            .order_by(Files.file_key, Files.tier_id)
            .subquery()
        )
        span = (last - first).total_seconds()
        if total <= max_frames or span == 0:
            step = None
            stmt = (
                select(unique_frames)
                .order_by(unique_frames.c.orig_ctime)
                .limit(max_frames)
            )
        else:
            step = span / max_frames
            bucket = func.least(
                func.floor(
                    (
                        func.extract(  # pylint: disable=not-callable
                            "epoch", unique_frames.c.orig_ctime
                        )
                        - first.timestamp()
                    )
                    / step
                ),
                max_frames - 1,
            )
            stmt = (
                select(unique_frames)
                .distinct(bucket)
                .order_by(bucket, unique_frames.c.orig_ctime)
            )
        rows = session.execute(stmt).all()

    return TimelapseFrames(
        total=total,
        step=step,
        frames=[
            TimelapseFrame(
                file_key=row.file_key, path=row.path, orig_ctime=row.orig_ctime
            )
            for row in rows
        ],
    )


def get_timelapse_summary(
    camera_identifiers: list[str],
    get_session: Callable[[], Session],
) -> dict[str, TimelapseSummary]:
    """Return a summary of the stored timelapse frames for each camera."""
    summary = {
        camera_identifier: TimelapseSummary(
            count=0, first=None, last=None, latest_frame=None
        )
        for camera_identifier in camera_identifiers
    }
    aggregates = (
        select(
            Files.camera_identifier,
            func.count(distinct(Files.file_key)).label(  # pylint: disable=not-callable
                "frame_count"
            ),
            func.min(Files.orig_ctime).label("first"),
            func.max(Files.orig_ctime).label("last"),
        )
        .where(*_timelapse_filter(camera_identifiers))
        .group_by(Files.camera_identifier)
        .subquery()
    )
    latest = (
        select(Files.camera_identifier, Files.file_key, Files.path, Files.orig_ctime)
        .where(*_timelapse_filter(camera_identifiers))
        .distinct(Files.camera_identifier)
        .order_by(Files.camera_identifier, Files.orig_ctime.desc(), Files.tier_id.asc())
        .subquery()
    )

    stmt = select(
        aggregates.c.camera_identifier,
        aggregates.c.frame_count,
        aggregates.c.first,
        aggregates.c.last,
        latest.c.file_key,
        latest.c.path,
        latest.c.orig_ctime,
    ).join(latest, latest.c.camera_identifier == aggregates.c.camera_identifier)
    with get_session() as session:
        rows = session.execute(stmt).all()
    for row in rows:
        summary[row.camera_identifier] = TimelapseSummary(
            count=row.frame_count,
            first=row.first,
            last=row.last,
            latest_frame=TimelapseFrame(
                file_key=row.file_key, path=row.path, orig_ctime=row.orig_ctime
            ),
        )
    return summary


def get_timelapse_days(
    camera_identifier: str,
    utc_offset: datetime.timedelta,
    get_session: Callable[[], Session],
) -> dict[str, int]:
    """Return the number of timelapse frames per day in the client's timezone."""
    local_date = func.date(Files.orig_ctime + utc_offset)
    with get_session() as session:
        rows = session.execute(
            select(
                local_date,
                func.count(distinct(Files.file_key)),  # pylint: disable=not-callable
            )
            .where(*_timelapse_filter([camera_identifier]))
            .group_by(local_date)
        ).all()
    return {day.isoformat(): count for day, count in rows}


def get_timelapse_frame_paths(
    camera_identifier: str,
    file_keys: list[int],
    get_session: Callable[[], Session],
) -> dict[int, list[str]]:
    """Return every stored path of the given timelapse frames, lowest tier first."""
    with get_session() as session:
        rows = session.execute(
            select(Files.file_key, Files.path)
            .where(*_timelapse_filter([camera_identifier]))
            .where(Files.file_key.in_(file_keys))
            .order_by(Files.file_key, Files.tier_id)
        ).all()
    paths: dict[int, list[str]] = {}
    for file_key, path in rows:
        paths.setdefault(file_key, []).append(path)
    return paths
