# pylint: disable=invalid-name
"""Add column adjusted_start_time to Recordings table.

Revision ID: 31851b6eb50c
Revises: 19a2457c5924
Create Date: 2024-08-12 06:33:58.432430

"""
from __future__ import annotations

import datetime

import sqlalchemy as sa
from alembic import op

from viseron.components.storage.models import Recordings, UTCDateTime
from viseron.const import CAMERA_SEGMENT_DURATION
from viseron.domains.camera.const import DEFAULT_LOOKBACK

# revision identifiers, used by Alembic.
revision: str | None = "31851b6eb50c"
down_revision: str | None = "19a2457c5924"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.add_column(
        "recordings",
        sa.Column(
            "adjusted_start_time",
            UTCDateTime(),
            nullable=True,
        ),
    )
    connection = op.get_bind()
    results = connection.execute(sa.select(Recordings)).fetchall()
    for result in results:
        adjusted_start_time = (
            result.start_time
            - datetime.timedelta(seconds=CAMERA_SEGMENT_DURATION)
            - datetime.timedelta(seconds=DEFAULT_LOOKBACK)
        )
        # Update the tier_path column with the generated tier path
        connection.execute(
            sa.update(Recordings)
            .where(Recordings.id == result.id)
            .values(
                adjusted_start_time=adjusted_start_time,
            )
        )
    op.alter_column("recordings", "adjusted_start_time", nullable=False)


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_column("recordings", "adjusted_start_time")
