# pylint: disable=invalid-name
"""Move event clips to /event_clips.

Revision ID: 7b1f82f2ec39
Revises: 620b4d1e5736
Create Date: 2025-02-06 07:11:12.890722

"""
from __future__ import annotations

import os
import shutil

import sqlalchemy as sa
from alembic import op

from viseron.components.storage.models import Files, Recordings
from viseron.helpers import create_directory

# revision identifiers, used by Alembic.
revision: str | None = "7b1f82f2ec39"
down_revision: str | None = "620b4d1e5736"
branch_labels: str | None = None
depends_on: str | None = None


def move_clip_to_new_folder(
    connection: sa.Connection,
    old_subcategory: str,
    new_subcategory: str,
    file_record: Files,
) -> None:
    """Move a clip to the new folder."""
    new_path = file_record.path.replace(old_subcategory, new_subcategory)
    new_dir = os.path.dirname(new_path)
    create_directory(new_dir)
    shutil.move(file_record.path, new_path)

    connection.execute(
        sa.update(Files)
        .where(Files.id == file_record.id)
        .values(path=new_path)
        .values(directory=new_dir)
        .values(subcategory=new_subcategory)
    )
    connection.execute(
        sa.update(Recordings)
        .where(Recordings.clip_path == file_record.path)
        .values(clip_path=new_path)
    )


def process_clip(old_subcategory: str, new_subcategory: str):
    """Move clips from old_subcategory to new_subcategory."""
    connection = op.get_bind()
    files = connection.execute(
        sa.select(Files)
        .where(Files.category == "recorder")
        .where(Files.subcategory == old_subcategory)
    )
    for file in files:
        if file.path.startswith(f"/{old_subcategory}"):
            if not os.path.exists(f"/{new_subcategory}"):
                raise ValueError(
                    f"The /{new_subcategory} folder does not exist. "
                    "Please mount it to the container."
                )

        try:
            move_clip_to_new_folder(
                connection,
                old_subcategory,
                new_subcategory,
                file,  # type: ignore[arg-type]
            )
        except Exception as e:  # pylint: disable=broad-except
            print(f"Failed to move {file.path} to {new_subcategory}. Error: {e}")
            print("Skipping this file, database will not be updated.")


def upgrade() -> None:
    """Run the upgrade migrations."""
    process_clip("recordings", "event_clips")


def downgrade() -> None:
    """Run the downgrade migrations."""
    process_clip("event_clips", "recordings")
