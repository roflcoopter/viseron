# pylint: disable=invalid-name
"""UTC timestamps as default.

Revision ID: 5e76f713b35c
Revises: 0b3b8178087f
Create Date: 2023-10-19 14:33:24.861265

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from viseron.components.storage.models import UTCNow

# revision identifiers, used by Alembic.
revision: str | None = "5e76f713b35c"
down_revision: str | None = "0b3b8178087f"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.alter_column("files", "created_at", server_default=UTCNow())
    op.alter_column("files_meta", "created_at", server_default=UTCNow())
    op.alter_column("recordings", "created_at", server_default=UTCNow())
    op.alter_column("objects", "created_at", server_default=UTCNow())
    op.alter_column("motion", "created_at", server_default=UTCNow())


def downgrade() -> None:
    """Run the downgrade migrations."""
    # pylint: disable=not-callable
    op.alter_column("files", "created_at", server_default=sa.func.now())
    op.alter_column("files_meta", "created_at", server_default=sa.func.now())
    op.alter_column("recordings", "created_at", server_default=sa.func.now())
    op.alter_column("objects", "created_at", server_default=sa.func.now())
    op.alter_column("motion", "created_at", server_default=sa.func.now())
