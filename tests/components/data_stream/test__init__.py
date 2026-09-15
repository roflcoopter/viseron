"""Tests for the data_stream component."""

from __future__ import annotations

import threading
import time
import uuid
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

import pytest
from tornado.queues import Queue as TornadoQueue

from viseron.components.data_stream import DataStream
from viseron.components.data_stream.const import DATA_QUEUE_MAXSIZE

if TYPE_CHECKING:
    from collections.abc import Callable

    from tornado.ioloop import IOLoop


class TestSubscribeData:
    """Test subscribe_data."""

    def test_returns_unique_ids(self, data_stream: DataStream) -> None:
        """Every subscription gets its own id."""
        first = data_stream.subscribe_data("topic", lambda _data: None)
        second = data_stream.subscribe_data("topic", lambda _data: None)
        assert first != second

    def test_literal_topic_does_not_match_other_topics(
        self, data_stream: DataStream
    ) -> None:
        """A subscription without a star only receives its exact topic."""
        queue: Queue = Queue()
        data_stream.subscribe_data("plain/topic", queue)
        data_stream.publish_data("plain/other", data="payload")

        with pytest.raises(Empty):
            queue.get(timeout=1)

    def test_invalid_subscriber_raises_at_subscribe_time(
        self, data_stream: DataStream
    ) -> None:
        """A non-callable, non-queue subscriber is rejected once, not per message."""
        subscriber: Any = "not a callback"
        with pytest.raises(ValueError, match="not a valid subscriber"):
            data_stream.subscribe_data("topic", subscriber)

    def test_tornado_queue_without_ioloop_is_rejected(
        self, data_stream: DataStream
    ) -> None:
        """A tornado queue is useless without an ioloop to put onto."""
        with pytest.raises(ValueError, match="requires an ioloop"):
            data_stream.subscribe_data("topic", TornadoQueue())


class TestCallbackSubscriber:
    """Test plain callable subscribers."""

    @pytest.mark.parametrize(
        ("publish_kwargs", "expected_args"),
        [
            pytest.param({}, (), id="no_data_calls_with_no_arguments"),
            pytest.param({"data": {"key": "value"}}, ({"key": "value"},), id="dict"),
            pytest.param({"data": {}}, ({},), id="falsy_empty_dict"),
            pytest.param({"data": []}, ([],), id="falsy_empty_list"),
            pytest.param({"data": 0}, (0,), id="falsy_zero"),
            pytest.param({"data": False}, (False,), id="falsy_false"),
            pytest.param({"data": ""}, ("",), id="falsy_empty_string"),
        ],
    )
    def test_callback_receives_published_data(
        self,
        data_stream: DataStream,
        wait_for: Callable[..., None],
        publish_kwargs: dict[str, Any],
        expected_args: tuple[Any, ...],
    ) -> None:
        """A callable subscriber is invoked with the published payload.

        Publishing without data invokes the callback with no arguments, which is
        what register_signal_handler relies on. A payload that is present but
        falsy must still be passed as an argument.
        """
        received: list[tuple[Any, ...]] = []
        done = threading.Event()

        def _callback(*args: Any) -> None:
            received.append(args)
            done.set()

        data_stream.subscribe_data("topic", _callback)
        data_stream.publish_data("topic", **publish_kwargs)

        wait_for(done)
        assert received == [expected_args]

    def test_all_subscribers_on_a_topic_are_invoked(
        self, data_stream: DataStream, wait_for: Callable[..., None]
    ) -> None:
        """Every subscriber on a topic receives the payload."""
        first = threading.Event()
        second = threading.Event()

        data_stream.subscribe_data("topic", lambda _data: first.set())
        data_stream.subscribe_data("topic", lambda _data: second.set())
        data_stream.publish_data("topic", data="payload")

        wait_for(first)
        wait_for(second)

    def test_messages_are_delivered_in_order(
        self, data_stream: DataStream, wait_for: Callable[..., None]
    ) -> None:
        """A slow first message must not overtake the messages behind it."""
        message_count = 20
        received: list[int] = []
        done = threading.Event()

        def _callback(data: int) -> None:
            if data == 0:
                time.sleep(0.2)
            received.append(data)
            if data == message_count - 1:
                done.set()

        data_stream.subscribe_data("topic", _callback)
        for index in range(message_count):
            data_stream.publish_data("topic", data=index)

        wait_for(done)
        assert received == list(range(message_count))

    @pytest.mark.parametrize(
        ("stage", "expected_daemon"),
        [
            pytest.param(None, True, id="no_stage_runs_daemon"),
            pytest.param("shutdown", False, id="stage_runs_non_daemon"),
        ],
    )
    def test_stage_controls_thread_daemon_flag(
        self,
        data_stream: DataStream,
        wait_for: Callable[..., None],
        stage: str | None,
        expected_daemon: bool,
    ) -> None:
        """Viseron.shutdown joins non-daemon threads tagged with a stage.

        See wait_for_threads_and_processes_to_exit in viseron/__init__.py.
        """
        observed: dict[str, Any] = {}
        done = threading.Event()

        def _callback(_data: Any) -> None:
            thread = threading.current_thread()
            observed["daemon"] = thread.daemon
            observed["stage"] = getattr(thread, "__stage__", None)
            done.set()

        data_stream.subscribe_data("topic", _callback, stage=stage)
        data_stream.publish_data("topic", data="payload")

        wait_for(done)
        assert observed["daemon"] is expected_daemon
        assert observed["stage"] == stage


class TestQueueSubscriber:
    """Test queue.Queue subscribers."""

    def test_queue_receives_published_data(self, data_stream: DataStream) -> None:
        """A queue subscriber has the payload put on it."""
        queue: Queue = Queue(maxsize=1)
        data_stream.subscribe_data("topic", queue)
        data_stream.publish_data("topic", data="payload")

        assert queue.get(timeout=5) == "payload"

    def test_full_queue_drops_oldest(
        self, data_stream: DataStream, wait_for: Callable[..., None]
    ) -> None:
        """A full subscriber queue drops its oldest entry rather than blocking."""
        queue: Queue = Queue(maxsize=1)
        queue.put("stale")
        settled = threading.Event()

        data_stream.subscribe_data("topic", queue)
        # Subscribers run in subscription order, so this fires after the queue
        # has been updated with the final payload.
        data_stream.subscribe_data(
            "topic", lambda data: settled.set() if data == "fresh_3" else None
        )

        for payload in ("fresh_1", "fresh_2", "fresh_3"):
            data_stream.publish_data("topic", data=payload)

        wait_for(settled)
        assert queue.qsize() == 1
        assert queue.get_nowait() == "fresh_3"


class TestTornadoQueueSubscriber:
    """Test tornado Queue subscribers."""

    def test_tornado_queue_receives_published_data(
        self, data_stream: DataStream, ioloop: IOLoop, wait_for: Callable[..., None]
    ) -> None:
        """A tornado queue subscriber with an ioloop has the payload put on it."""
        queue: TornadoQueue = TornadoQueue(maxsize=1)
        received: list[Any] = []
        done = threading.Event()

        async def _fetch() -> None:
            received.append(await queue.get())
            done.set()

        data_stream.subscribe_data("topic", queue, ioloop=ioloop)
        ioloop.add_callback(_fetch)
        data_stream.publish_data("topic", data="payload")

        wait_for(done)
        assert received == ["payload"]


class TestIOLoopCallbackSubscriber:
    """Test callable subscribers dispatched onto an ioloop."""

    def test_sync_callback_runs(
        self, data_stream: DataStream, ioloop: IOLoop, wait_for: Callable[..., None]
    ) -> None:
        """A synchronous callable with an ioloop receives the payload."""
        received: list[Any] = []
        done = threading.Event()

        def _callback(data: Any) -> None:
            received.append(data)
            done.set()

        data_stream.subscribe_data("topic", _callback, ioloop=ioloop)
        data_stream.publish_data("topic", data="payload")

        wait_for(done)
        assert received == ["payload"]

    def test_async_callback_runs(
        self, data_stream: DataStream, ioloop: IOLoop, wait_for: Callable[..., None]
    ) -> None:
        """A coroutine function with an ioloop receives the payload."""
        received: list[Any] = []
        done = threading.Event()

        async def _callback(data: Any) -> None:
            received.append(data)
            done.set()

        data_stream.subscribe_data("topic", _callback, ioloop=ioloop)
        data_stream.publish_data("topic", data="payload")

        wait_for(done)
        assert received == ["payload"]


class TestWildcardSubscriptions:
    """Test wildcard topic matching."""

    @pytest.mark.parametrize(
        ("pattern", "topic", "expect_delivery"),
        [
            pytest.param("camera/*/event", "camera/one/event", True, id="single_star"),
            pytest.param("domain/setup/*/*/*", "domain/setup/a/b/c", True, id="three"),
            pytest.param("camera/*/event", "camera/one/other", False, id="no_match"),
            pytest.param(
                "camera/*/event", "camera/a/b/event", True, id="star_spans_separators"
            ),
        ],
    )
    def test_wildcard_matching(
        self,
        data_stream: DataStream,
        pattern: str,
        topic: str,
        expect_delivery: bool,
    ) -> None:
        """Wildcard subscribers are selected with fnmatch semantics."""
        queue: Queue = Queue()
        data_stream.subscribe_data(pattern, queue)
        data_stream.publish_data(topic, data="payload")

        delivered = True
        try:
            queue.get(timeout=1)
        except Empty:
            delivered = False
        assert delivered is expect_delivery

    def test_static_and_wildcard_subscribers_both_invoked(
        self, data_stream: DataStream
    ) -> None:
        """A message reaches static and wildcard subscribers alike."""
        static_queue: Queue = Queue()
        wildcard_queue: Queue = Queue()
        data_stream.subscribe_data("camera/one/event", static_queue)
        data_stream.subscribe_data("camera/*/event", wildcard_queue)

        data_stream.publish_data("camera/one/event", data="payload")

        assert static_queue.get(timeout=5) == "payload"
        assert wildcard_queue.get(timeout=5) == "payload"


class TestUnsubscribe:
    """Test unsubscribe_data and remove_all_subscriptions."""

    @pytest.mark.parametrize(
        "topic",
        [
            pytest.param("plain/topic", id="static_topic"),
            pytest.param("wild/*/topic", id="wildcard_topic"),
        ],
    )
    def test_unsubscribe_stops_delivery(
        self, data_stream: DataStream, topic: str
    ) -> None:
        """After unsubscribing, no further data is delivered."""
        queue: Queue = Queue()
        unique_id = data_stream.subscribe_data(topic, queue)
        data_stream.unsubscribe_data(topic, unique_id)

        data_stream.publish_data(topic.replace("*", "any"), data="payload")

        with pytest.raises(Empty):
            queue.get(timeout=1)

    @pytest.mark.parametrize(
        "topic",
        [
            pytest.param("camera_1/event", id="static_topic"),
            pytest.param("camera_1/*/event", id="wildcard_topic"),
        ],
    )
    def test_unsubscribe_prunes_empty_topics(
        self, data_stream: DataStream, topic: str
    ) -> None:
        """The registry must not grow monotonically with per-camera topic names."""
        unique_id = data_stream.subscribe_data(topic, lambda _data: None)
        assert DataStream._registry.topic_count == 1

        data_stream.unsubscribe_data(topic, unique_id)

        assert DataStream._registry.topic_count == 0

    def test_remove_all_subscriptions_stops_static_and_wildcard_delivery(
        self, data_stream: DataStream
    ) -> None:
        """remove_all_subscriptions drops static and wildcard subscribers alike."""
        static_queue: Queue = Queue()
        wildcard_queue: Queue = Queue()
        data_stream.subscribe_data("plain/topic", static_queue)
        data_stream.subscribe_data("wild/*/topic", wildcard_queue)

        data_stream.remove_all_subscriptions()

        data_stream.publish_data("plain/topic", data="payload")
        data_stream.publish_data("wild/any/topic", data="payload")

        with pytest.raises(Empty):
            static_queue.get(timeout=1)
        with pytest.raises(Empty):
            wildcard_queue.get(timeout=1)

    def test_unsubscribe_unknown_topic_does_not_raise(
        self, data_stream: DataStream
    ) -> None:
        """Unsubscribing from a topic that was never subscribed to is a no-op.

        Every unsub() closure handed out by Viseron.listen_event is called
        during teardown, which happens after Viseron.shutdown has already
        called remove_all_subscriptions.
        """
        data_stream.unsubscribe_data("never/subscribed", uuid.uuid4())

    def test_unsubscribe_after_remove_all_does_not_raise(
        self, data_stream: DataStream
    ) -> None:
        """The unsub closure still works after remove_all_subscriptions."""
        unique_id = data_stream.subscribe_data("topic", lambda _data: None)
        data_stream.remove_all_subscriptions()

        data_stream.unsubscribe_data("topic", unique_id)


class TestSignalTopics:
    """Shutdown signals must survive a saturated data queue."""

    def test_signal_queue_is_unbounded_while_data_queue_drops(
        self, stopped_data_stream: DataStream
    ) -> None:
        """Flooding the bus must not be able to discard a shutdown signal."""
        overflow = DATA_QUEUE_MAXSIZE + 50
        for index in range(overflow):
            stopped_data_stream.publish_data("some/data/topic", data=index)
        for index in range(overflow):
            stopped_data_stream.publish_data("viseron/signal/shutdown", data=index)

        assert DataStream._data_queue.qsize() == DATA_QUEUE_MAXSIZE
        assert DataStream._signal_queue.qsize() == overflow

    def test_signals_are_drained_ahead_of_a_data_backlog(
        self, stopped_data_stream: DataStream
    ) -> None:
        """The consumer handles pending signals before it touches queued data."""
        delivered: Queue = Queue()
        stopped_data_stream.subscribe_data("some/data/topic", delivered)
        stopped_data_stream.subscribe_data("viseron/signal/shutdown", delivered)

        for index in range(500):
            stopped_data_stream.publish_data("some/data/topic", data=f"data_{index}")
        stopped_data_stream.publish_data("viseron/signal/shutdown", data="signal")

        stopped_data_stream._drain_signals()

        assert delivered.get_nowait() == "signal"

    def test_a_signal_is_delivered_to_a_shutdown_stage_subscriber(
        self, data_stream: DataStream, wait_for: Callable[..., None]
    ) -> None:
        """A signal reaches its handler through the separate signal queue."""
        seen = threading.Event()
        data_stream.subscribe_data(
            "viseron/signal/shutdown", seen.set, stage="shutdown"
        )

        data_stream.publish_data("viseron/signal/shutdown")

        wait_for(seen)


class TestStop:
    """Test stopping the data stream."""

    def test_stop_ends_the_consumer_thread(self) -> None:
        """stop() followed by join() terminates the consumer thread."""
        stream = DataStream(object())
        stream.stop()
        stream.join()
        assert not stream._data_consumer.is_alive()
