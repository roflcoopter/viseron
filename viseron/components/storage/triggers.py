"""Set up database triggers."""

import logging

from sqlalchemy import Connection, event
from sqlalchemy.dialects.postgresql import insert

from viseron.components.storage.models import Files, FilesMeta
from viseron.helpers import utcnow

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
                orig_ctime=utcnow(),
                meta={},
            )
            .on_conflict_do_nothing(index_elements=["path"])
        )


def setup_triggers(engine) -> None:
    """Set up database triggers."""
    event.listen(engine, "before_execute", insert_into_files_meta)
