"""Add index to Files table to improve tier check performance.

Revision ID: a6397b8c2fc9
Revises: 7b1f82f2ec39
Create Date: 2025-06-19 12:11:00.911576

"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "a6397b8c2fc9"
down_revision: str | None = "7b1f82f2ec39"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.create_index(
        "idx_files_tier_lookup",
        "files",
        ["camera_identifier", "tier_id", "category", "subcategory"],
        unique=False,
    )


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_index("idx_files_tier_lookup", table_name="files")
