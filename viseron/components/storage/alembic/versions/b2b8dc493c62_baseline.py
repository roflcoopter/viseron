# pylint: disable=invalid-name
"""Baseline.

Revision ID: b2b8dc493c62
Revises: None
Create Date: 2023-05-08 14:12:53.478955

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b2b8dc493c62"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tier_id", sa.Integer(), nullable=False),
        sa.Column("camera_identifier", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False, unique=True),
        sa.Column("directory", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_table("files")
