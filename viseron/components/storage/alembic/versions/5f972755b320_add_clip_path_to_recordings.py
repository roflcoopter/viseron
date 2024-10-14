# pylint: disable=invalid-name
"""Add clip_path to Recordings.

Revision ID: 5f972755b320
Revises: 57a2e296a424
Create Date: 2024-04-04 21:00:26.008974

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "5f972755b320"
down_revision: str | None = "57a2e296a424"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.add_column("recordings", sa.Column("clip_path", sa.String(), nullable=True))


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_column("recordings", "clip_path")
