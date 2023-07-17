"""Viseron fixtures."""
from typing import Any, Generator, Iterator
from unittest.mock import MagicMock, patch

import pytest
from pytest_postgresql import factories
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from viseron import Viseron
from viseron.components.data_stream import COMPONENT as DATA_STREAM, DataStream
from viseron.components.storage.models import Base

test_db = factories.postgresql_proc(port=None, dbname="test_db")


@pytest.fixture
def vis() -> Viseron:
    """Fixture to test Viseron instance."""
    viseron = Viseron()
    viseron.data[DATA_STREAM] = MagicMock(spec=DataStream)
    return viseron


@pytest.fixture(scope="session", autouse=True)
def patch_enable_logging() -> Iterator[None]:
    """Patch enable_logging to avoid adding duplicate handlers."""
    with patch("viseron.enable_logging"):
        yield


def _make_db_session(database) -> Generator[Session, Any, None]:
    """Create a DB session."""
    with DatabaseJanitor(
        database.user,
        database.host,
        database.port,
        database.dbname,
        database.version,
        database.password,
    ):
        connection_str = (
            "postgresql+psycopg2://"
            f"{database.user}:@{database.host}:{database.port}/{database.dbname}"
        )
        engine = create_engine(connection_str)
        Base.metadata.create_all(engine)
        _sessionmaker = sessionmaker(bind=engine, expire_on_commit=False)
        with _sessionmaker() as session:
            yield session
        Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(test_db):
    """Session for SQLAlchemy."""
    yield from _make_db_session(test_db)


@pytest.fixture(scope="class")
def db_session_class(test_db):
    """Session for SQLAlchemy."""
    yield from _make_db_session(test_db)
