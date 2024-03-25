# pylint: disable=invalid-name
"""Add subcategory column to Files table.

Revision ID: 57a2e296a424
Revises: b04d8eb3aa4c
Create Date: 2024-03-04 09:22:52.057132

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "57a2e296a424"
down_revision: str | None = "18b341b50c58"
branch_labels: str | None = None
depends_on: str | None = None


def generate_subcategory(tier_path, directory, category) -> str:
    """Generate the subcategory from the directory."""
    # Remove the tier_path from the beginning directory
    directory = directory.replace(tier_path, "")
    # Remove leading and trailing slashes
    directory = directory.strip("/")
    # Split the directory into parts
    parts = directory.split("/")
    # Categories has different amounts of parent folders
    index_offset = 0
    if category == "snapshots":
        index_offset = 1
    return parts[index_offset]


def upgrade() -> None:
    """Run the upgrade migrations."""
    op.alter_column(
        "recordings", "thumbnail_path", existing_type=sa.VARCHAR(), nullable=True
    )

    op.add_column("files", sa.Column("subcategory", sa.String(), nullable=True))
    # Declare ORM table view of the NEW database table.
    t_files = sa.Table(
        "files",
        sa.MetaData(),
        sa.Column("id", sa.Integer()),
        sa.Column("tier_id", sa.String()),
        sa.Column("tier_path", sa.String()),
        sa.Column("camera_identifier", sa.String()),
        sa.Column("category", sa.String()),
        sa.Column("subcategory", sa.String()),  # New column
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
        subcategory = generate_subcategory(
            result.tier_path, result.directory, result.category
        )
        # Update the tier_path column with the generated tier path
        connection.execute(
            t_files.update()
            .where(t_files.c.id == result.id)
            .values(
                subcategory=subcategory,
            )
        )
    op.alter_column("files", "subcategory", nullable=False)


def downgrade() -> None:
    """Run the downgrade migrations."""
    op.alter_column(
        "recordings", "thumbnail_path", existing_type=sa.VARCHAR(), nullable=False
    )
    op.drop_column("files", "subcategory")
