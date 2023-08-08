"""Set up database triggers."""

import logging
import os

from sqlalchemy import Connection, delete, event
from sqlalchemy.dialects.postgresql import insert

from viseron.components.storage.models import Files, FilesMeta, Recordings

LOGGER = logging.getLogger(__name__)


def insert_into_files_meta(
    conn: Connection,
    clauseelement,
    _multiparams,
    _params,
    _execution_options,
) -> None:
    """Insert a row into FilesMeta when a new row is inserted into Files."""
    if clauseelement.is_insert and clauseelement.table.name == Files.__tablename__:
        compiled = clauseelement.compile()
        conn.execute(
            insert(FilesMeta)
            .values(
                path=compiled.params["path"],
                meta={},
            )
            .on_conflict_do_nothing(index_elements=["path"])
        )


def delete_from_files_meta(
    conn: Connection,
    clauseelement,
    _multiparams,
    _params,
    _execution_options,
) -> None:
    """Delete a row from FilesMeta when a row is deleted from Files."""
    if clauseelement.is_delete and clauseelement.table.name == Files.__tablename__:
        compiled = clauseelement.compile()
        conn.execute(
            delete(FilesMeta).where(FilesMeta.path == compiled.params["path_1"])
        )


def delete_thumbnail(
    _conn: Connection,
    clauseelement,
    _multiparams,
    _params,
    _execution_options,
) -> None:
    """Delete a thumbnail when a row is deleted from Recordings."""
    if clauseelement.is_delete and clauseelement.table.name == Recordings.__tablename__:
        compiled = clauseelement.compile()
        try:
            os.remove(compiled.params["path_1"])
        except FileNotFoundError as error:
            LOGGER.error(
                f"Failed to delete thumbnail {compiled.params['path_1']}: {error}"
            )


def setup_triggers(engine) -> None:
    """Set up database triggers."""
    event.listen(engine, "before_execute", insert_into_files_meta)
    event.listen(engine, "after_execute", delete_from_files_meta)

    event.listen(engine, "before_execute", delete_thumbnail)
