"""Drop and recreate the database."""

import sys
from typing import Literal

from sqlalchemy import create_engine

from viseron.components.storage.const import DATABASE_URL
from viseron.components.storage.models import Base


def _drop_alemibc_version_table(engine):
    """Manually drop alembic_version table as it is not part of the models."""
    connection = engine.raw_connection()
    cursor = connection.cursor()
    command = "DROP TABLE IF EXISTS alembic_version;"
    cursor.execute(command)
    connection.commit()
    cursor.close()


def main() -> Literal[0]:
    """Drop and recreate the database."""
    print("Dropping tables.")
    engine = create_engine(DATABASE_URL)
    Base.metadata.drop_all(engine)
    _drop_alemibc_version_table(engine)
    print("Creating tables.")
    Base.metadata.create_all(engine)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
