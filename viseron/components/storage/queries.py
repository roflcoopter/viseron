"""Database queries."""

import logging

from sqlalchemy import Integer, String, TextualSelect, column, text

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
            SELECT id
                  ,tier_id
                  ,camera_identifier
                  ,category
                  ,path
                  ,created_at
                  ,sum(size) FILTER (
                      WHERE category = :category
                        AND tier_id = :tier_id
                        AND camera_identifier = :camera_identifier
                  ) OVER win1 AS total_bytes
              FROM files
            WINDOW win1 AS (
                PARTITION BY category, tier_id
                ORDER BY created_at DESC
                RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            )
            ORDER BY created_at DESC
        )
        SELECT id, path
          FROM size_sum
         WHERE tier_id = :tier_id
           AND camera_identifier = :camera_identifier
           AND category = :category
           AND (
               :max_bytes > 0 AND
               total_bytes >= :max_bytes AND
               created_at <= to_timestamp(:min_age_timestamp)
           ) OR (
               :max_age_timestamp > 0 AND
               created_at <= to_timestamp(:max_age_timestamp) AND
               total_bytes >= :min_bytes
           )
        ORDER BY created_at ASC;
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
                  ,f.filename
                  ,f.created_at as file_created_at
                  ,f.size
                  ,r.id as recording_id
                  ,r.created_at as recording_created_at
              FROM files f
         LEFT JOIN recordings r
                ON substr(f.filename, 1, 10) BETWEEN cast(
                  extract(
                    epoch
                    from
                      (
                        r.start_time - INTERVAL ':lookback sec'
                                     - INTERVAL ':segment_length sec'
                      )
                  ) as char(10)
                )
                AND cast(
                  extract(
                    epoch
                    from
                      case when r.end_time is null then now() else (
                        r.end_time + INTERVAL ':segment_length sec'
                      ) end
                  ) as char(10)
                )
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
         ORDER BY rf.filename ASC
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
