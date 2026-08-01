"""Viseron fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
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
from viseron.const import FAILED, LOADED, LOADING

from tests.common import MockCamera

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator

    from pytest_postgresql.executor import PostgreSQLExecutor

test_db = factories.postgresql_proc(port=None, dbname="test_db")


class MockViseron(Viseron):
    """Protocol for mocking Viseron.

    Provides mocked versions of commonly-used methods to avoid side effects
    during testing. This includes event dispatching, entity registration,
    and event listening.
    """

    def __init__(self) -> None:
        super().__init__(start_background_scheduler=False)
        self.register_domain: Mock = Mock(
            side_effect=self.register_domain,
        )
        self.mocked_register_domain = self.register_domain
        self.add_entity: MagicMock = MagicMock(
            auto_spec=self.add_entity,
        )
        self.listen_event: MagicMock = MagicMock(
            auto_spec=self.listen_event,
        )
        self.dispatch_event: MagicMock = MagicMock(
            auto_spec=self.dispatch_event,
        )
        self.initialized_event.set()
        self._original_register_signal_handler = self.register_signal_handler
        self.register_signal_handler: MagicMock = MagicMock(
            side_effect=self._original_register_signal_handler
        )


@pytest.fixture
def vis() -> MockViseron:
    """Fixture to test Viseron instance."""
    viseron = MockViseron()
    viseron.data[DATA_STREAM] = MagicMock(spec=DataStream)
    viseron.data[STORAGE] = MagicMock(spec=Storage)
    viseron.data[STORAGE].file_batch_size = (  # type: ignore[misc]
        DEFAULT_TIER_CHECK_BATCH_SIZE
    )
    viseron.data[WEBSERVER] = MagicMock(spec=Webserver)
    viseron.data[LOADED] = {}
    viseron.data[LOADING] = {}
    viseron.data[FAILED] = {}

    return viseron


@pytest.fixture
def camera() -> MockCamera:
    """Fixture to test camera."""
    return MockCamera()


@pytest.fixture(scope="session", autouse=True)
def patch_tier_check_worker() -> Iterator[None]:
    """Patch TierCheckWorker to prevent real subprocesses from spawning in tests."""
    with patch("viseron.components.storage.TierCheckWorker"):
        yield


@pytest.fixture(scope="session", autouse=True)
def patch_enable_logging() -> Iterator[None]:
    """Patch enable_logging to avoid adding duplicate handlers."""
    with patch("viseron.enable_logging"):
        yield


def _make_db_session(database: PostgreSQLExecutor) -> Generator[Session, Any, None]:
    """Create a DB session."""
    with DatabaseJanitor(
        user=database.user,
        host=database.host,
        port=database.port,
        dbname=database.dbname,
        version=database.version,
        password=database.password,
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


def _get_db_session(
    database: PostgreSQLExecutor,
) -> Generator[sessionmaker[Session], Any, None]:
    """Create a DB session."""
    with DatabaseJanitor(
        user=database.user,
        host=database.host,
        port=database.port,
        dbname=database.dbname,
        version=database.version,
        password=database.password,
    ):
        connection_str = (
            "postgresql+psycopg2://"
            f"{database.user}:@{database.host}:{database.port}/{database.dbname}"
        )
        engine = create_engine(connection_str)
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine, expire_on_commit=False)
        Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(test_db: PostgreSQLExecutor):
    """Session for SQLAlchemy."""
    yield from _make_db_session(test_db)


@pytest.fixture(scope="class")
def db_session_class(test_db: PostgreSQLExecutor):
    """Session for SQLAlchemy."""
    yield from _make_db_session(test_db)


@pytest.fixture
def get_db_session(test_db: PostgreSQLExecutor):
    """Session for SQLAlchemy with function scope."""
    yield from _get_db_session(test_db)


@pytest.fixture(scope="class")
def get_db_session_class(test_db: PostgreSQLExecutor):
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
def alembic_engine(test_db: PostgreSQLExecutor):
    """Return engine for pytest-alembic."""
    with DatabaseJanitor(
        user=test_db.user,
        host=test_db.host,
        port=test_db.port,
        dbname=test_db.dbname,
        version=test_db.version,
        password=test_db.password,
    ):
        connection_str = (
            "postgresql+psycopg2://"
            f"{test_db.user}:@{test_db.host}:{test_db.port}/{test_db.dbname}"
        )
        yield create_engine(connection_str)


CONTAINER_TESTS_DIR = Path(__file__).parent / "container"


def _is_inside_container_tests(path: Path) -> bool:
    """Return True if path is the container smoke test dir or below it."""
    try:
        path.resolve().relative_to(CONTAINER_TESTS_DIR.resolve())
    except ValueError:
        return False
    return True


def _container_tests_requested(config: pytest.Config) -> bool:
    """Return True if the user explicitly requested tests/container."""
    rootpath = Path(config.rootpath)

    for arg in config.args:
        path_arg = arg.split("::", 1)[0]
        candidate = Path(path_arg)
        if not candidate.is_absolute():
            candidate = rootpath / candidate

        if _is_inside_container_tests(candidate):
            return True

    return False


def pytest_ignore_collect(
    collection_path: Path,
    config: pytest.Config,
) -> bool | None:
    """Skip container smoke tests unless explicitly requested."""
    if _is_inside_container_tests(collection_path) and not _container_tests_requested(
        config
    ):
        return True

    return None
