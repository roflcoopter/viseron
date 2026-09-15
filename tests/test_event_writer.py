"""Test the batched event writer."""

from __future__ import annotations

import datetime
import threading
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from viseron.components.storage.models import Events
from viseron.event_writer import EventWriter

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def session() -> MagicMock:
    """Return a mocked SQLAlchemy session."""
    return MagicMock()


@pytest.fixture
def storage(session: MagicMock) -> MagicMock:
    """Return a mocked Storage whose get_session yields the mocked session."""
    mock = MagicMock()
    mock.get_session.return_value.__enter__.return_value = session
    mock.get_session.return_value.__exit__.return_value = False
    return mock


@pytest.fixture
def event_writer(storage: MagicMock) -> Generator[EventWriter]:
    """Yield a running EventWriter."""
    writer = EventWriter(storage)
    yield writer
    writer.stop()


def _timestamp() -> datetime.datetime:
    return datetime.datetime(2026, 8, 17, 12, 0, tzinfo=datetime.timezone.utc)


class TestEventWriter:
    """Test EventWriter."""

    def test_stop_flushes_pending_events(
        self, event_writer: EventWriter, session: MagicMock
    ) -> None:
        """Events queued but not yet written are persisted on stop."""
        event_writer.enqueue("event_1", "{}", _timestamp())
        event_writer.stop()

        rows = _written_rows(session)
        assert [row["name"] for row in rows] == ["event_1"]

    def test_multiple_events_are_written_as_one_batch(
        self, event_writer: EventWriter, session: MagicMock
    ) -> None:
        """A burst of events costs a single insert rather than one per event."""
        for index in range(50):
            event_writer.enqueue(f"event_{index}", "{}", _timestamp())
        event_writer.stop()

        assert session.execute.call_count == 1
        rows = _written_rows(session)
        assert len(rows) == 50

    def test_event_timestamp_is_preserved(
        self, event_writer: EventWriter, session: MagicMock
    ) -> None:
        """Batching must not backdate events to the flush time."""
        event_writer.enqueue("event_1", "{}", _timestamp())
        event_writer.stop()

        assert _written_rows(session)[0]["created_at"] == _timestamp()

    def test_a_database_error_does_not_kill_the_writer(
        self, storage: MagicMock, session: MagicMock
    ) -> None:
        """A failed batch is logged and the writer keeps accepting events."""
        session.execute.side_effect = [RuntimeError("boom"), None]
        writer = EventWriter(storage)

        writer.enqueue("event_1", "{}", _timestamp())
        writer.flush()
        writer.enqueue("event_2", "{}", _timestamp())
        writer.stop()

        assert session.execute.call_count == 2

    def test_enqueue_does_not_write_on_the_calling_thread(
        self, storage: MagicMock
    ) -> None:
        """The publisher must never block on a database round trip."""
        writing_thread: list[str] = []
        storage.get_session.side_effect = lambda: (
            writing_thread.append(threading.current_thread().name) or MagicMock()
        )

        writer = EventWriter(storage)
        writer.enqueue("event_1", "{}", _timestamp())
        writer.stop()

        assert writing_thread
        assert threading.current_thread().name not in writing_thread


def _written_rows(session: MagicMock) -> list[dict]:
    """Return every row passed to session.execute across all calls."""
    rows: list[dict] = []
    for call in session.execute.call_args_list:
        rows.extend(call.args[1])
    return rows


class TestEventWriterAgainstPostgres:
    """Exercise the insert against a real database.

    The mocked tests above would still pass with a malformed statement.
    """

    def test_batch_is_persisted(self, get_db_session: sessionmaker[Session]) -> None:
        """A batch of events is written and readable back."""
        storage = MagicMock()
        storage.get_session = get_db_session
        writer = EventWriter(storage)

        for index in range(5):
            writer.enqueue(f"event_{index}", '{"key": "value"}', _timestamp())
        writer.stop()

        with get_db_session() as session:
            rows = session.execute(select(Events).order_by(Events.name)).scalars().all()

        assert [row.name for row in rows] == [f"event_{index}" for index in range(5)]
        # The column is JSONB but the payload has always been stored as a JSON
        # string scalar rather than an object.
        assert rows[0].data == '{"key": "value"}'
        assert rows[0].created_at == _timestamp()
