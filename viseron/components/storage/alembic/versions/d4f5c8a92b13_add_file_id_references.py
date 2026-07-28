"""Add file id references to path-backed event artifacts.

Revision ID: d4f5c8a92b13
Revises: 7f6d3739fcd6
Create Date: 2026-07-04 23:30:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "d4f5c8a92b13"
down_revision: str | None = "7f6d3739fcd6"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Add nullable file id references and backfill exact path matches."""
    op.add_column(
        "recordings", sa.Column("thumbnail_file_id", sa.Integer(), nullable=True)
    )
    op.add_column("recordings", sa.Column("clip_file_id", sa.Integer(), nullable=True))
    op.add_column("objects", sa.Column("snapshot_file_id", sa.Integer(), nullable=True))
    op.add_column("motion", sa.Column("snapshot_file_id", sa.Integer(), nullable=True))
    op.add_column(
        "post_processor_results",
        sa.Column("snapshot_file_id", sa.Integer(), nullable=True),
    )

    op.execute(
        """
        UPDATE recordings
        SET thumbnail_file_id = files.id
        FROM files
        WHERE recordings.thumbnail_path = files.path
        """
    )
    op.execute(
        """
        UPDATE recordings
        SET clip_file_id = files.id
        FROM files
        WHERE recordings.clip_path = files.path
        """
    )
    op.execute(
        """
        UPDATE objects
        SET snapshot_file_id = files.id
        FROM files
        WHERE objects.snapshot_path = files.path
        """
    )
    op.execute(
        """
        UPDATE motion
        SET snapshot_file_id = files.id
        FROM files
        WHERE motion.snapshot_path = files.path
        """
    )
    op.execute(
        """
        UPDATE post_processor_results
        SET snapshot_file_id = files.id
        FROM files
        WHERE post_processor_results.snapshot_path = files.path
        """
    )

    op.create_index(
        "idx_recordings_thumbnail_file_id",
        "recordings",
        ["thumbnail_file_id"],
        unique=False,
    )
    op.create_index(
        "idx_recordings_clip_file_id", "recordings", ["clip_file_id"], unique=False
    )
    op.create_index(
        "idx_objects_snapshot_file_id", "objects", ["snapshot_file_id"], unique=False
    )
    op.create_index(
        "idx_motion_snapshot_file_id", "motion", ["snapshot_file_id"], unique=False
    )
    op.create_index(
        "idx_ppr_snapshot_file_id",
        "post_processor_results",
        ["snapshot_file_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_recordings_thumbnail_file_id_files",
        "recordings",
        "files",
        ["thumbnail_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_recordings_clip_file_id_files",
        "recordings",
        "files",
        ["clip_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_objects_snapshot_file_id_files",
        "objects",
        "files",
        ["snapshot_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_motion_snapshot_file_id_files",
        "motion",
        "files",
        ["snapshot_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_ppr_snapshot_file_id_files",
        "post_processor_results",
        "files",
        ["snapshot_file_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove nullable file id references."""
    op.drop_constraint(
        "fk_ppr_snapshot_file_id_files",
        "post_processor_results",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_motion_snapshot_file_id_files", "motion", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_objects_snapshot_file_id_files", "objects", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_recordings_clip_file_id_files", "recordings", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_recordings_thumbnail_file_id_files", "recordings", type_="foreignkey"
    )

    op.drop_index("idx_ppr_snapshot_file_id", table_name="post_processor_results")
    op.drop_index("idx_motion_snapshot_file_id", table_name="motion")
    op.drop_index("idx_objects_snapshot_file_id", table_name="objects")
    op.drop_index("idx_recordings_clip_file_id", table_name="recordings")
    op.drop_index("idx_recordings_thumbnail_file_id", table_name="recordings")

    op.drop_column("post_processor_results", "snapshot_file_id")
    op.drop_column("motion", "snapshot_file_id")
    op.drop_column("objects", "snapshot_file_id")
    op.drop_column("recordings", "clip_file_id")
    op.drop_column("recordings", "thumbnail_file_id")
