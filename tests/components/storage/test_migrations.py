"""Test database migrations."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from pytest_alembic.tests import *  # pylint: disable=unused-wildcard-import,wildcard-import # noqa: F401, F403
from sqlalchemy import text

if TYPE_CHECKING:
    from pytest_alembic import MigrationContext
    from sqlalchemy import Engine

FILE_KEY_REVISION = "0aad2bea54e5"


def _file_row(file_id: int) -> dict[str, object]:
    return {
        "id": file_id,
        "tier_id": 0,
        "tier_path": "/tier0",
        "camera_identifier": "camera",
        "category": "recorder",
        "subcategory": "segments",
        "path": f"/tier0/recorder/segments/camera/{file_id}.m4s",
        "directory": "/tier0/recorder/segments/camera",
        "filename": f"{file_id}.m4s",
        "size": 10,
        "orig_ctime": datetime.datetime(2026, 1, 1),
    }


def test_file_key_backfill(
    alembic_runner: MigrationContext, alembic_engine: Engine
) -> None:
    """Test that existing rows get distinct keys and new rows do not reuse them."""
    alembic_runner.migrate_up_before(FILE_KEY_REVISION)
    alembic_runner.insert_into("files", [_file_row(i) for i in (1, 2, 3)])
    alembic_runner.migrate_up_one()

    with alembic_engine.begin() as connection:
        backfilled = connection.execute(text("SELECT file_key FROM files")).scalars()
        backfilled_keys = set(backfilled)
        connection.execute(
            text(
                "INSERT INTO files (id, tier_id, tier_path, camera_identifier, "
                "category, subcategory, path, directory, filename, size, orig_ctime) "
                "VALUES (4, 0, '/tier0', 'camera', 'recorder', 'segments', "
                "'/tier0/4.m4s', '/tier0', '4.m4s', 10, now())"
            )
        )
        new_key = connection.execute(
            text("SELECT file_key FROM files WHERE id = 4")
        ).scalar_one()

    assert len(backfilled_keys) == 3
    assert None not in backfilled_keys
    assert new_key not in backfilled_keys
