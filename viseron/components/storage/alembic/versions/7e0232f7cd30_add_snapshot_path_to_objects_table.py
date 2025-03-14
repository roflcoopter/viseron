# pylint: disable=invalid-name
"""Add snapshot_path to Objects table.

Revision ID: 7e0232f7cd30
Revises: bef4c78cc3b0
Create Date: 2024-01-15 15:09:52.459281

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "7e0232f7cd30"
down_revision: str | None = "bef4c78cc3b0"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.add_column("objects", sa.Column("snapshot_path", sa.String(), nullable=True))


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_column("objects", "snapshot_path")
