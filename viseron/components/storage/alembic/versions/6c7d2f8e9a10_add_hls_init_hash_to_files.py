"""Add HLS init hash to files.

Revision ID: 6c7d2f8e9a10
Revises: e9f3a2c1d4b5
Create Date: 2026-07-10 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "6c7d2f8e9a10"
down_revision: str | None = "e9f3a2c1d4b5"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Add nullable HLS init hash to file metadata."""
    op.add_column("files", sa.Column("hls_init_hash", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove HLS init hash from file metadata."""
    op.drop_column("files", "hls_init_hash")
