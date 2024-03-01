# pylint: disable=invalid-name
"""Add tier_path column.

Revision ID: 18b341b50c58
Revises: 7e0232f7cd30
Create Date: 2024-02-26 17:22:01.800057

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "18b341b50c58"
down_revision: str | None = "7e0232f7cd30"
branch_labels: str | None = None
depends_on: str | None = None


def generate_tier_path(path: str, camera_identifier: str, category: str) -> str:
    """Generate the tier path from the path, camera identifier and category."""
    # Split the path into parts
    parts = path.split("/")

    # Find the index of the camera identifier in the parts list
    try:
        index = parts.index(camera_identifier)
    except ValueError:
        return path

    # Categories has different amounts of parent folders
    index_offset = 0
    if category == "recorder":
        index_offset = 1
    if category == "snapshots":
        index_offset = 2

    # Join the parts of the path before the camera identifier and return
    if tier_path := "/".join(parts[: index - index_offset]):
        return tier_path
    return "/"


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.add_column("files", sa.Column("tier_path", sa.String()))

    # Declare ORM table view of the NEW database table.
    t_files = sa.Table(
        "files",
        sa.MetaData(),
        sa.Column("id", sa.Integer()),
        sa.Column("tier_id", sa.String()),
        sa.Column("tier_path", sa.String()),  # New column
        sa.Column("camera_identifier", sa.String()),
        sa.Column("category", sa.String()),
        sa.Column("path", sa.String()),
        sa.Column("directory", sa.String()),
        sa.Column("filename", sa.String()),
        sa.Column("size", sa.Integer()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )

    connection = op.get_bind()
    results = connection.execute(t_files.select()).fetchall()
    for result in results:
        tier_path = generate_tier_path(
            result.path, result.camera_identifier, result.category
        )
        # Update the tier_path column with the generated tier path
        connection.execute(
            t_files.update()
            .where(t_files.c.id == result.id)
            .values(
                tier_path=tier_path,
            )
        )


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.drop_column("files", "tier_path")
