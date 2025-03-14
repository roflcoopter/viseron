# pylint: disable=invalid-name
"""Add PostProcessorResults table.

Revision ID: 8462ca6851b2
Revises: 5f972755b320
Create Date: 2024-05-27 22:10:05.321288

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from viseron.components.storage.models import UTCDateTime

# revision identifiers, used by Alembic.
revision: str | None = "8462ca6851b2"
down_revision: str | None = "5f972755b320"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.create_table(
        "post_processor_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_identifier", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("snapshot_path", sa.String(), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            UTCDateTime(),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column("updated_at", UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_table("post_processor_results")
