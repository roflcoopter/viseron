"""Batched persistence of dispatched events."""

from __future__ import annotations

import logging
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

from sqlalchemy import insert

from viseron.components.storage.models import Events
from viseron.helpers import pop_if_full
from viseron.watchdog.thread_watchdog import RestartableThread

if TYPE_CHECKING:
    import datetime

    from viseron.components.storage import Storage

LOGGER = logging.getLogger(__name__)

QUEUE_MAXSIZE = 5000
BATCH_SIZE = 100
POLL_TIMEOUT = 0.5


class EventWriter:
    """Persist dispatched events off the publishing thread.

    Every stored event used to cost the dispatching thread a round trip to
    Postgres. States.set_state stores its events, so entity state changes made
    the frame pipeline wait on the database.
    """

    def __init__(self, storage: Storage) -> None:
        self._storage = storage
        self._queue: Queue[dict[str, Any]] = Queue(maxsize=QUEUE_MAXSIZE)
        self._kill_received = False
        self._thread = RestartableThread(
            name="event_writer", target=self._run, daemon=True, register=True
        )
        self._thread.start()

    def enqueue(self, name: str, data_json: str, created_at: datetime.datetime) -> None:
        """Queue an event for persistence."""
        pop_if_full(
            self._queue,
            {"name": name, "data": data_json, "created_at": created_at},
            logger=LOGGER,
            name="event_writer",
            warn=True,
        )

    def flush(self) -> None:
        """Write every queued event immediately."""
        batch = self._collect_batch(block=False)
        while batch:
            self._write(batch)
            batch = self._collect_batch(block=False)

    def stop(self) -> None:
        """Stop the writer, flushing anything still queued."""
        if self._kill_received:
            return
        self._kill_received = True
        self._thread.join(timeout=10)
        self.flush()

    def _run(self) -> None:
        while not self._kill_received:
            batch = self._collect_batch(block=True)
            if batch:
                self._write(batch)
        LOGGER.debug("Event writer stopped")

    def _collect_batch(self, block: bool) -> list[dict[str, Any]]:
        batch: list[dict[str, Any]] = []
        if block:
            try:
                batch.append(self._queue.get(timeout=POLL_TIMEOUT))
            except Empty:
                return batch

        while len(batch) < BATCH_SIZE:
            try:
                batch.append(self._queue.get_nowait())
            except Empty:
                break
        return batch

    def _write(self, batch: list[dict[str, Any]]) -> None:
        try:
            with self._storage.get_session() as session:
                session.execute(insert(Events), batch)
                session.commit()
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(f"Failed to write {len(batch)} events to the database")
