# pylint: disable=invalid-name
"""Add indexes for cleanup jobs.

Revision ID: 19e8b884f943
Revises: 31851b6eb50c
Create Date: 2024-11-12 11:04:52.728159

"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "19e8b884f943"
down_revision: str | None = "31851b6eb50c"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.create_index("idx_files_camera_id", "files", ["camera_identifier"], unique=False)
    op.create_index("idx_files_path", "files", ["path"], unique=False)
    op.create_index(
        "idx_files_meta_orig_ctime", "files_meta", ["orig_ctime"], unique=False
    )
    op.create_index("idx_files_meta_path", "files_meta", ["path"], unique=False)
    op.create_index("idx_motion_snapshot", "motion", ["snapshot_path"], unique=False)
    op.create_index("idx_objects_snapshot", "objects", ["snapshot_path"], unique=False)
    op.create_index(
        "idx_ppr_snapshot", "post_processor_results", ["snapshot_path"], unique=False
    )
    op.create_index(
        "idx_recordings_camera_times",
        "recordings",
        ["camera_identifier", "start_time", "end_time"],
        unique=False,
    )
    op.create_index("idx_recordings_clip", "recordings", ["clip_path"], unique=False)
    op.create_index(
        "idx_recordings_thumbnail", "recordings", ["thumbnail_path"], unique=False
    )


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_index("idx_recordings_thumbnail", table_name="recordings")
    op.drop_index("idx_recordings_clip", table_name="recordings")
    op.drop_index("idx_recordings_camera_times", table_name="recordings")
    op.drop_index("idx_ppr_snapshot", table_name="post_processor_results")
    op.drop_index("idx_objects_snapshot", table_name="objects")
    op.drop_index("idx_motion_snapshot", table_name="motion")
    op.drop_index("idx_files_meta_path", table_name="files_meta")
    op.drop_index("idx_files_meta_orig_ctime", table_name="files_meta")
    op.drop_index("idx_files_path", table_name="files")
    op.drop_index("idx_files_camera_id", table_name="files")
