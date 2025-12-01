"""Viseron fixtures."""
from __future__ import annotations

from collections.abc import Generator, Iterator
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from pytest_postgresql import factories
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from viseron import Viseron
from viseron.components.data_stream import COMPONENT as DATA_STREAM, DataStream
from viseron.components.storage import COMPONENT as STORAGE, Storage
from viseron.components.storage.const import DEFAULT_TIER_CHECK_BATCH_SIZE
from viseron.components.storage.models import Base
from viseron.components.webserver import COMPONENT as WEBSERVER, Webserver
from viseron.const import LOADED

from tests.common import MockCamera

test_db = factories.postgresql_proc(port=None, dbname="test_db")


class MockViseron(Viseron):
    """Protocol for mocking Viseron."""

    def __init__(self) -> None:
        super().__init__(start_background_scheduler=False)
        self.register_domain = Mock(  # type: ignore[method-assign]
            side_effect=self.register_domain,
        )
        self.mocked_register_domain = self.register_domain
        self.add_entity = MagicMock(  # type: ignore[method-assign]
            auto_spec=self.add_entity,
        )


@pytest.fixture
def vis() -> MockViseron:
    """Fixture to test Viseron instance."""
    viseron = MockViseron()
    viseron.data[DATA_STREAM] = MagicMock(spec=DataStream)
    viseron.data[STORAGE] = MagicMock(spec=Storage)
    viseron.data[STORAGE].file_batch_size = DEFAULT_TIER_CHECK_BATCH_SIZE
    viseron.data[WEBSERVER] = MagicMock(spec=Webserver)
    viseron.data[LOADED] = {}

    return viseron


@pytest.fixture
def camera() -> MockCamera:
    """Fixture to test camera."""
    return MockCamera()


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


def _get_db_session(database) -> Generator[sessionmaker[Session], Any, None]:
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
        yield sessionmaker(bind=engine, expire_on_commit=False)
        Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(test_db):
    """Session for SQLAlchemy."""
    yield from _make_db_session(test_db)


@pytest.fixture(scope="class")
def db_session_class(test_db):
    """Session for SQLAlchemy."""
    yield from _make_db_session(test_db)


@pytest.fixture(scope="function")
def get_db_session(test_db):
    """Session for SQLAlchemy with function scope."""
    yield from _get_db_session(test_db)


@pytest.fixture(scope="class")
def get_db_session_class(test_db):
    """Session for SQLAlchemy with class scope."""
    yield from _get_db_session(test_db)


@pytest.fixture
def alembic_config() -> dict[str, str]:
    """Return config for pytest-alembic."""
    return {
        "file": "viseron/components/storage/alembic.ini",
        "script_location": "viseron/components/storage/alembic",
    }


@pytest.fixture
def alembic_engine(test_db):
    """Return engine for pytest-alembic."""
    with DatabaseJanitor(
        test_db.user,
        test_db.host,
        test_db.port,
        test_db.dbname,
        test_db.version,
        test_db.password,
    ):
        connection_str = (
            "postgresql+psycopg2://"
            f"{test_db.user}:@{test_db.host}:{test_db.port}/{test_db.dbname}"
        )
        yield create_engine(connection_str)
