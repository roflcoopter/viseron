# pylint: disable=invalid-name
"""Add triggertypes Enum.

Revision ID: 117d07971f1a
Revises: 8462ca6851b2
Create Date: 2024-06-26 21:32:34.037301

"""
from __future__ import annotations

from enum import Enum

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "117d07971f1a"
down_revision: str | None = "8462ca6851b2"
branch_labels: str | None = None
depends_on: str | None = None


class TriggerTypes(Enum):
    """Trigger types for recordings."""

    MOTION = "motion"
    OBJECT = "object"


def upgrade() -> None:
    """Run the upgrade migrations."""
    triggertypes_enum = sa.Enum(TriggerTypes, name="triggertypes")
    triggertypes_enum.create(op.get_bind(), checkfirst=False)
    op.execute(
        "ALTER TABLE recordings ALTER COLUMN trigger_type TYPE triggertypes"
        " USING trigger_type::text::triggertypes"
    )


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.execute(
        "ALTER TABLE recordings ALTER COLUMN trigger_type TYPE text"
        " USING trigger_type::text"
    )
    sa.Enum(name="triggertypes").drop(op.get_bind(), checkfirst=False)
