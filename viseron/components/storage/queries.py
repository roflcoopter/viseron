"""Database queries."""

import logging

from sqlalchemy import Integer, String, TextualSelect, column, text

LOGGER = logging.getLogger(__name__)


def files_to_move_query(
    category: str,
    tier_id: int,
    camera_identifier: str,
    max_bytes: int,
    min_age_seconds: float,
    min_bytes: int,
    max_age_seconds: float,
) -> TextualSelect:
    """Return query for files to move to next tier or delete."""
    LOGGER.debug(
        "Query bindparms: category(%s), tier_id(%s), camera_identifier(%s), "
        "max_bytes(%s), min_age_seconds(%s), min_bytes(%s), max_age_seconds(%s)",
        category,
        tier_id,
        camera_identifier,
        max_bytes,
        min_age_seconds,
        min_bytes,
        max_age_seconds,
    )
    return (
        text(
            """
        WITH size_sum AS (
            SELECT
                id
                ,tier_id
                ,camera_identifier
                ,category
                ,path
                ,created_at
                ,sum(size) FILTER (
                    WHERE category = :category
                    AND   tier_id = :tier_id
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
        AND   camera_identifier = :camera_identifier
        AND   category = :category
        AND ((
            :max_bytes > 0 AND
            total_bytes >= :max_bytes AND
            created_at <= to_timestamp(:min_age_seconds)
        ) OR (
            :max_age_seconds > 0 AND
            created_at <= to_timestamp(:max_age_seconds) AND
            total_bytes >= :min_bytes
        ))
        ORDER BY created_at ASC
    """
        )
        .bindparams(
            category=category,
            tier_id=tier_id,
            camera_identifier=camera_identifier,
            max_bytes=max_bytes,
            min_age_seconds=min_age_seconds,
            min_bytes=min_bytes,
            max_age_seconds=max_age_seconds,
        )
        .columns(
            column("id", Integer),
            column("path", String),
        )
    )
