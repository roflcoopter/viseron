"""Test the pop_if_full helper."""

from __future__ import annotations

from queue import Empty, Full, Queue
from unittest.mock import MagicMock, patch

import pytest

from viseron.helpers import pop_if_full


class TestPopIfFull:
    """Test pop_if_full."""

    def test_puts_on_an_empty_queue(self) -> None:
        """An item is put straight onto a queue with room."""
        queue: Queue = Queue(maxsize=1)
        pop_if_full(queue, "item")
        assert queue.get_nowait() == "item"

    def test_full_queue_keeps_the_newest_item(self) -> None:
        """The oldest item is discarded to make room for the newest."""
        queue: Queue = Queue(maxsize=1)
        queue.put("stale")

        pop_if_full(queue, "fresh")

        assert queue.qsize() == 1
        assert queue.get_nowait() == "fresh"

    def test_does_not_sleep_after_making_room(self) -> None:
        """Popping the oldest item already frees the slot, so do not back off.

        Frame pipeline queues use maxsize=1, so a sleep here throttles every
        publisher that overtakes its consumer.
        """
        queue: Queue = Queue(maxsize=1)
        queue.put("stale")

        with patch("viseron.helpers.time.sleep") as sleep_mock:
            pop_if_full(queue, "fresh")

        sleep_mock.assert_not_called()

    def test_backs_off_when_another_consumer_took_the_slot(self) -> None:
        """Losing the race to another consumer backs off before retrying."""
        queue = MagicMock()
        queue.put_nowait.side_effect = [Full, None]
        queue.get_nowait.side_effect = Empty

        with patch("viseron.helpers.time.sleep") as sleep_mock:
            pop_if_full(queue, "item")

        sleep_mock.assert_called_once()
        assert queue.put_nowait.call_count == 2

    def test_gives_up_after_max_attempts(self) -> None:
        """A queue that stays full raises Full rather than looping forever."""
        queue = MagicMock()
        queue.put_nowait.side_effect = Full
        queue.get_nowait.side_effect = Empty

        with patch("viseron.helpers.time.sleep"), pytest.raises(Full):
            pop_if_full(queue, "item", max_attempts=3)

    def test_warns_when_requested(self) -> None:
        """warn=True logs which queue is dropping data."""
        queue: Queue = Queue(maxsize=1)
        queue.put("stale")
        logger = MagicMock()

        pop_if_full(queue, "fresh", logger=logger, name="test_queue", warn=True)

        logger.warning.assert_called_once()
