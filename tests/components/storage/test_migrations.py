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
TIMELAPSE_ORIG_CTIME_REVISION = "3de25eba5ef4"
INSERT_TIME = datetime.datetime(2026, 1, 1)


def _file_row(
    file_id: int,
    category: str = "recorder",
    subcategory: str = "segments",
    filename: str | None = None,
) -> dict[str, object]:
    filename = filename or f"{file_id}.m4s"
    directory = f"/tier0/{category}/{subcategory}/camera"
    return {
        "id": file_id,
        "tier_id": 0,
        "tier_path": "/tier0",
        "camera_identifier": "camera",
        "category": category,
        "subcategory": subcategory,
        "path": f"{directory}/{filename}",
        "directory": directory,
        "filename": filename,
        "size": 10,
        "orig_ctime": INSERT_TIME,
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


def test_timelapse_orig_ctime_backfill(
    alembic_runner: MigrationContext, alembic_engine: Engine
) -> None:
    """Test that timelapse frames get the timestamp from their filename."""
    alembic_runner.migrate_up_before(TIMELAPSE_ORIG_CTIME_REVISION)
    alembic_runner.insert_into(
        "files",
        [
            _file_row(1, "timelapse", "timelapse", "1723111156.jpg"),
            _file_row(2, "timelapse", "timelapse", "not_an_epoch.jpg"),
            _file_row(1723111161),
        ],
    )
    alembic_runner.migrate_up_one()

    with alembic_engine.begin() as connection:
        rows = dict(
            connection.execute(text("SELECT id, orig_ctime FROM files")).tuples().all()
        )

    assert rows == {
        1: datetime.datetime(2024, 8, 8, 9, 59, 16),
        2: INSERT_TIME,
        1723111161: INSERT_TIME,
    }
