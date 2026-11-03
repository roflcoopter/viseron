# pylint: disable=invalid-name
"""Backfill timelapse orig_ctime and index files by orig_ctime.

Revision ID: 3de25eba5ef4
Revises: 0aad2bea54e5
Create Date: 2026-09-24 08:00:00.000000

"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "3de25eba5ef4"
down_revision: str | None = "0aad2bea54e5"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Run the upgrade migrations."""
    # Frames used to be stored with their insert time, but are named <epoch>.jpg
    op.execute(
        """
        UPDATE files
        SET orig_ctime = to_timestamp(split_part(filename, '.', 1)::bigint)
            AT TIME ZONE 'UTC'
        WHERE category = 'timelapse'
          AND subcategory = 'timelapse'
          AND filename ~ '^[0-9]+\\.jpg$'
        """
    )
    op.create_index(
        "idx_files_orig_ctime_lookup",
        "files",
        ["camera_identifier", "category", "subcategory", "orig_ctime"],
        unique=False,
    )


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_index("idx_files_orig_ctime_lookup", table_name="files")
