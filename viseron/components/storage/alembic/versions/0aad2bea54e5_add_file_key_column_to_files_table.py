# pylint: disable=invalid-name
"""Add file_key column to files table.

Revision ID: 0aad2bea54e5
Revises: 7f6d3739fcd6
Create Date: 2026-09-18 07:29:00.684915

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "0aad2bea54e5"
down_revision: str | None = "7f6d3739fcd6"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.execute(sa.schema.CreateSequence(sa.Sequence("files_file_key_seq")))
    op.add_column(
        "files",
        sa.Column(
            "file_key",
            sa.BigInteger(),
            server_default=sa.text("nextval('files_file_key_seq')"),
            nullable=False,
        ),
    )
    op.create_index("idx_files_file_key", "files", ["file_key"], unique=False)
    op.create_index(
        "idx_files_name_lookup",
        "files",
        ["camera_identifier", "category", "subcategory", "filename"],
        unique=False,
    )


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_index("idx_files_name_lookup", table_name="files")
    op.drop_index("idx_files_file_key", table_name="files")
    op.drop_column("files", "file_key")
    op.execute(sa.schema.DropSequence(sa.Sequence("files_file_key_seq")))
