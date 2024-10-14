"""Add MotionContours table.

Revision ID: bef4c78cc3b0
Revises: 523864b2bd20
Create Date: 2023-12-14 10:21:09.234959

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "bef4c78cc3b0"
down_revision: str | None = "523864b2bd20"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.create_table(
        "motion_contours",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("motion_id", sa.Integer(), nullable=False),
        sa.Column("contour", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("motion", sa.Column("end_time", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_column("motion", "end_time")
    op.drop_table("motion_contours")
