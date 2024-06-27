# pylint: disable=invalid-name
"""Add snapshot_path to Motion table.

Revision ID: 19a2457c5924
Revises: 117d07971f1a
Create Date: 2024-06-27 08:52:25.442683

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "19a2457c5924"
down_revision: str | None = "117d07971f1a"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.add_column("motion", sa.Column("snapshot_path", sa.String(), nullable=True))


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_column("motion", "snapshot_path")
