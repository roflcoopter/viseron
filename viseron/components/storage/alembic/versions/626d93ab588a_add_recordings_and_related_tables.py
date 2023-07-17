# pylint: disable=invalid-name
"""Add Recordings and related tables.

Revision ID: 626d93ab588a
Revises: b2b8dc493c62
Create Date: 2023-06-19 13:03:50.071980

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "626d93ab588a"
down_revision: str | None = "b2b8dc493c62"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.create_table(
        "motion",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_identifier", sa.String(), nullable=False),
        sa.Column("start_time", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "objects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_identifier", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("x1", sa.Float(), nullable=False),
        sa.Column("y1", sa.Float(), nullable=False),
        sa.Column("x2", sa.Float(), nullable=False),
        sa.Column("y2", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "recordings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_identifier", sa.String(), nullable=False),
        sa.Column("start_time", sa.Integer(), nullable=False),
        sa.Column("end_time", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("trigger_type", sa.String(), nullable=True),
        sa.Column("trigger_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_table("recordings")
    op.drop_table("objects")
    op.drop_table("motion")
