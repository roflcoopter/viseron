"""Database queries."""
from __future__ import annotations

import datetime
import logging
from typing import Callable

from sqlalchemy import (
    Integer,
    String,
    TextualSelect,
    and_,
    cast,
    column,
    desc,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import INTERVAL
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import coalesce, concat

from viseron.components.storage.models import Files, FilesMeta, Recordings
from viseron.helpers import utcnow

LOGGER = logging.getLogger(__name__)


def files_to_move_query(
    category: str,
    tier_id: int,
    camera_identifier: str,
    max_bytes: int,
    min_age_timestamp: float,
    min_bytes: int,
    max_age_timestamp: float,
) -> TextualSelect:
    """Return query for files to move to next tier or delete."""
    LOGGER.debug(
        "Query bindparms: category(%s), tier_id(%s), camera_identifier(%s), "
        "max_bytes(%s), min_age_timestamp(%s), min_bytes(%s), max_age_timestamp(%s)",
        category,
        tier_id,
        camera_identifier,
        max_bytes,
        min_age_timestamp,
        min_bytes,
        max_age_timestamp,
    )
    return (
        text(
            """--sql
        WITH size_sum AS (
            SELECT f.id
                  ,f.tier_id
                  ,f.camera_identifier
                  ,f.category
                  ,f.path
                  ,fm.orig_ctime
                  ,sum(f.size) FILTER (
                      WHERE f.category = :category
                        AND f.tier_id = :tier_id
                        AND f.camera_identifier = :camera_identifier
                  ) OVER win1 AS total_bytes
              FROM files f
              JOIN files_meta fm
                ON f.path = fm.path
            WINDOW win1 AS (
                PARTITION BY f.category, f.tier_id
                ORDER BY fm.orig_ctime DESC
                RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            )
            ORDER BY fm.orig_ctime DESC
        )
        SELECT id, path
          FROM size_sum
         WHERE tier_id = :tier_id
           AND camera_identifier = :camera_identifier
           AND category = :category
           AND (
               :max_bytes > 0 AND
               total_bytes >= :max_bytes AND
               orig_ctime <= to_timestamp(:min_age_timestamp)
           ) OR (
               :max_age_timestamp > 0 AND
               orig_ctime <= to_timestamp(:max_age_timestamp) AND
               total_bytes >= :min_bytes
           )
        ORDER BY orig_ctime ASC;
    """
        )
        .bindparams(
            category=category,
            tier_id=tier_id,
            camera_identifier=camera_identifier,
            max_bytes=max_bytes,
            min_age_timestamp=min_age_timestamp,
            min_bytes=min_bytes,
            max_age_timestamp=max_age_timestamp,
        )
        .columns(
            column("id", Integer),
            column("path", String),
        )
    )


def recordings_to_move_query(
    segment_length: int,
    tier_id: int,
    camera_identifier: str,
    lookback: int,
    max_bytes: int,
    min_age_timestamp: float,
    min_bytes: int,
    max_age_timestamp: float,
) -> TextualSelect:
    """Return query for segments to move to next tier or delete."""
    return (
        text(
            """--sql
        WITH recording_files as (
            SELECT f.id as file_id
                  ,f.tier_id
                  ,f.camera_identifier
                  ,f.category
                  ,f.path
                  ,f.size
                  ,r.id as recording_id
                  ,r.created_at as recording_created_at
                  ,meta.orig_ctime
              FROM files f
              JOIN files_meta meta
                ON f.path = meta.path
         LEFT JOIN recordings r
                ON meta.orig_ctime BETWEEN
                    r.start_time - INTERVAL ':lookback sec'
                                 - INTERVAL ':segment_length sec' AND
                    COALESCE(r.end_time + INTERVAL ':segment_length sec', now())
             WHERE f.category = 'recorder'
               AND f.tier_id = :tier_id
               AND f.camera_identifier = :camera_identifier
        ),

        recordings_size AS (
            SELECT recording_id
                  ,sum(size) as recording_size
              FROM recording_files
          GROUP BY recording_id
        ),

        size_sum AS (
            SELECT r.id
                  ,sum(rs.recording_size) OVER (
                        ORDER BY r.created_at DESC
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                   ) AS total_bytes
              FROM recordings r
                   JOIN recordings_size rs
                   ON r.id = rs.recording_id
        )
        SELECT rf.recording_id
              ,rf.file_id
              ,rf.path
          FROM recording_files rf
               LEFT JOIN size_sum s
               ON rf.recording_id = s.id
         WHERE (
            (
                :max_bytes > 0 AND
                s.total_bytes >= :max_bytes AND
                rf.recording_created_at <= to_timestamp(:min_age_timestamp)
            ) OR (
                :max_age_timestamp > 0 AND
                rf.recording_created_at <= to_timestamp(:max_age_timestamp) AND
                s.total_bytes >= :min_bytes
            )
        ) OR s.total_bytes IS NULL
         ORDER BY rf.orig_ctime ASC
                 ,rf.recording_created_at ASC;
        """
        )
        .bindparams(
            tier_id=tier_id,
            camera_identifier=camera_identifier,
            segment_length=segment_length,
            max_bytes=max_bytes,
            min_age_timestamp=min_age_timestamp,
            max_age_timestamp=max_age_timestamp,
            min_bytes=min_bytes,
            lookback=lookback,
        )
        .columns(
            column("recording_id", Integer),
            column("file_id", Integer),
            column("path", String),
        )
    )


def get_recording_fragments(
    recording_id,
    lookback: float,
    get_session: Callable[[], Session],
    now=utcnow(),
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
        select(Files, FilesMeta)
        .add_columns(row_number)
        .join(Recordings, Files.camera_identifier == Recordings.camera_identifier)
        .join(FilesMeta, Files.path == FilesMeta.path)
        .where(Recordings.id == recording_id)
        .where(Files.category == "recorder")
        .where(Files.path.endswith(".m4s"))
        .where(
            or_(
                # Fetch all files that start within the recording
                FilesMeta.orig_ctime.between(
                    Recordings.start_time - datetime.timedelta(seconds=lookback),
                    coalesce(Recordings.end_time, now),
                ),
                # Fetch the first file that starts before the recording but
                # ends during the recording
                and_(
                    Recordings.start_time - datetime.timedelta(seconds=lookback)
                    >= FilesMeta.orig_ctime,
                    Recordings.start_time - datetime.timedelta(seconds=lookback)
                    <= FilesMeta.orig_ctime
                    + cast(
                        concat(FilesMeta.meta["m3u8"]["EXTINF"], " sec"),
                        INTERVAL,
                    ),
                ),
            )
        )
        .order_by(FilesMeta.orig_ctime.asc())
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