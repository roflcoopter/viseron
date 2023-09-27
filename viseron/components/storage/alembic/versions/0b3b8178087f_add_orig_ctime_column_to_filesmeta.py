# pylint: disable=invalid-name
"""Add orig_ctime column to FilesMeta.

Revision ID: 0b3b8178087f
Revises: 6b1ef9a6220a
Create Date: 2023-09-19 06:41:24.278740

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "0b3b8178087f"
down_revision: str | None = "6b1ef9a6220a"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.add_column("files_meta", sa.Column("orig_ctime", sa.DateTime(), nullable=False))


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_column("files_meta", "orig_ctime")
