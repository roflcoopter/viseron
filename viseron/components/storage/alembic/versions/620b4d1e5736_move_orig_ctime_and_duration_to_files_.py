# pylint: disable=invalid-name
"""Move orig_ctime and duration to Files table.

Revision ID: 620b4d1e5736
Revises: 19e8b884f943
Create Date: 2025-01-10 15:29:37.628544

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from viseron.components.storage.models import UTCDateTime

# revision identifiers, used by Alembic.
revision: str | None = "620b4d1e5736"
down_revision: str | None = "19e8b884f943"
branch_labels: str | None = None
depends_on: str | None = None


def set_orig_ctime() -> None:
    """Move orig_ctime to Files table."""
    op.execute(
        "UPDATE files "
        "SET orig_ctime = ("
        "SELECT orig_ctime FROM files_meta WHERE files_meta.path = files.path"
        ");"
    )


def set_duration() -> None:
    """Move duration to Files table."""
    # duration is stored in the JSONB column "meta", with the key "m3u8" > "EXTINF"
    op.execute(
        "UPDATE files "
        "SET duration = ("
        "SELECT (meta->'m3u8'->'EXTINF')::float "
        "FROM files_meta WHERE files_meta.path = files.path"
        ")"
    )


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.add_column("files", sa.Column("duration", sa.Float(), nullable=True))
    op.add_column(
        "files",
        sa.Column(
            "orig_ctime",
            UTCDateTime(),
            nullable=True,
        ),
    )

    set_orig_ctime()
    set_duration()

    op.execute("DELETE FROM files WHERE orig_ctime IS NULL")
    op.alter_column("files", "orig_ctime", nullable=False)

    op.drop_index("idx_files_meta_orig_ctime", table_name="files_meta")
    op.drop_index("idx_files_meta_path", table_name="files_meta")
    op.drop_table("files_meta")


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_column("files", "orig_ctime")
    op.drop_column("files", "duration")

    op.create_table(
        "files_meta",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("path", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column(
            "orig_ctime", postgresql.TIMESTAMP(), autoincrement=False, nullable=False
        ),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("timezone('utc'::text, CURRENT_TIMESTAMP)"),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(), autoincrement=False, nullable=True
        ),
        sa.PrimaryKeyConstraint("id", name="files_meta_pkey"),
        sa.UniqueConstraint("path", name="files_meta_path_key"),
    )
    op.create_index("idx_files_meta_path", "files_meta", ["path"], unique=False)
    op.create_index(
        "idx_files_meta_orig_ctime", "files_meta", ["orig_ctime"], unique=False
    )
