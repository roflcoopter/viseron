# pylint: disable=invalid-name
"""Add FilesMeta table.

Revision ID: 6b1ef9a6220a
Revises: 626d93ab588a
Create Date: 2023-07-31 13:25:14.139973

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str | None = "6b1ef9a6220a"
down_revision: str | None = "626d93ab588a"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.create_table(
        "files_meta",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path"),
    )


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_table("files_meta")
