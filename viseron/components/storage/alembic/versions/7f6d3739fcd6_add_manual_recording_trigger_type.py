# pylint: disable=invalid-name
"""Add manual recording trigger type.

Revision ID: 7f6d3739fcd6
Revises: a6397b8c2fc9
Create Date: 2025-11-24 06:33:20.406378

"""
from __future__ import annotations

from enum import Enum

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "7f6d3739fcd6"
down_revision: str | None = "a6397b8c2fc9"
branch_labels: str | None = None
depends_on: str | None = None


class OldTriggerTypes(Enum):
    """Old trigger types for recordings."""

    MOTION = "motion"
    OBJECT = "object"


class NewTriggerTypes(Enum):
    """New trigger types for recordings."""

    MOTION = "motion"
    OBJECT = "object"
    MANUAL = "manual"


def upgrade() -> None:
    """Run the upgrade migrations."""
    # Recreate old enum as tmp_triggertypes, convert column, then drop 'triggertypes'
    triggertypes_enum = sa.Enum(OldTriggerTypes, name="tmp_triggertypes")
    triggertypes_enum.create(op.get_bind(), checkfirst=False)
    op.execute(
        "ALTER TABLE recordings ALTER COLUMN trigger_type TYPE tmp_triggertypes"
        " USING trigger_type::text::tmp_triggertypes"
    )
    sa.Enum(name="triggertypes").drop(op.get_bind(), checkfirst=False)

    # Create new enum as triggertypes, convert column, then drop 'tmp_triggertypes'
    new_triggertypes_enum = sa.Enum(NewTriggerTypes, name="triggertypes")
    new_triggertypes_enum.create(op.get_bind(), checkfirst=False)
    op.execute(
        "ALTER TABLE recordings ALTER COLUMN trigger_type TYPE triggertypes"
        " USING trigger_type::text::triggertypes"
    )
    sa.Enum(name="tmp_triggertypes").drop(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    """Run the downgrade migrations."""
    # Delete any rows with 'manual' trigger_type
    op.execute("DELETE FROM recordings WHERE trigger_type = 'MANUAL'")

    # Recreate new enum as tmp_triggertypes, convert column, then drop 'triggertypes'
    new_triggertypes_enum = sa.Enum(NewTriggerTypes, name="tmp_triggertypes")
    new_triggertypes_enum.create(op.get_bind(), checkfirst=False)
    op.execute(
        "ALTER TABLE recordings ALTER COLUMN trigger_type TYPE tmp_triggertypes"
        " USING trigger_type::text::tmp_triggertypes"
    )
    sa.Enum(name="triggertypes").drop(op.get_bind(), checkfirst=False)

    # Create old enum as triggertypes, convert column, then drop 'tmp_triggertypes'
    triggertypes_enum = sa.Enum(OldTriggerTypes, name="triggertypes")
    triggertypes_enum.create(op.get_bind(), checkfirst=False)
    op.execute(
        "ALTER TABLE recordings ALTER COLUMN trigger_type TYPE triggertypes"
        " USING trigger_type::text::triggertypes"
    )
    sa.Enum(name="tmp_triggertypes").drop(op.get_bind(), checkfirst=False)
