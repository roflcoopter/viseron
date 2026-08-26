"""Subscriber representation for the data_stream component."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from enum import IntEnum, auto
from queue import Queue
from typing import TYPE_CHECKING, Any

from tornado.queues import Queue as TornadoQueue

if TYPE_CHECKING:
    import uuid
    from collections.abc import Callable

    from tornado.ioloop import IOLoop

    from viseron.components.data_stream.delivery import SerialDelivery


class SubscriberKind(IntEnum):
    """How a subscriber wants its data delivered."""

    CALLBACK = auto()
    SIGNAL_CALLBACK = auto()
    IOLOOP_CALLBACK = auto()
    IOLOOP_COROUTINE = auto()
    QUEUE = auto()
    TORNADO_QUEUE = auto()


@dataclass(slots=True, eq=False)
class Subscriber:
    """A single subscription with its delivery strategy resolved up front.

    Resolving the kind, the thread name and coroutine-ness here keeps the
    publish path free of introspection, which runs for every message.
    """

    unique_id: uuid.UUID
    data_topic: str
    callback: Callable | Queue | TornadoQueue
    ioloop: IOLoop | None
    stage: str | None
    kind: SubscriberKind
    thread_name: str | None = None
    delivery: SerialDelivery | None = field(default=None, repr=False)


def resolve_kind(
    callback: Callable | Queue | TornadoQueue,
    ioloop: IOLoop | None,
    stage: str | None,
) -> SubscriberKind:
    """Determine how a subscriber must be invoked.

    Raises:
        ValueError: If the subscriber could never be delivered to.
    """
    if isinstance(callback, TornadoQueue):
        if ioloop is None:
            raise ValueError(
                f"Tornado Queue subscriber {callback} requires an ioloop to be "
                "delivered to"
            )
        return SubscriberKind.TORNADO_QUEUE

    if isinstance(callback, Queue):
        return SubscriberKind.QUEUE

    if callable(callback):
        if ioloop is not None:
            if inspect.iscoroutinefunction(callback):
                return SubscriberKind.IOLOOP_COROUTINE
            return SubscriberKind.IOLOOP_CALLBACK
        if stage is not None:
            return SubscriberKind.SIGNAL_CALLBACK
        return SubscriberKind.CALLBACK

    raise ValueError(
        f"{callback} of type {type(callback)} is not a valid subscriber. "
        "Needs to be of type Callable, Queue or Tornado Queue with ioloop supplied"
    )


def create_subscriber(
    unique_id: uuid.UUID,
    data_topic: str,
    callback: Callable | Queue | TornadoQueue,
    ioloop: IOLoop | None,
    stage: str | None,
) -> Subscriber:
    """Build a Subscriber, validating that it can be delivered to."""
    kind = resolve_kind(callback, ioloop, stage)
    thread_name: str | None = None
    if kind is SubscriberKind.SIGNAL_CALLBACK:
        thread_name = f"data_stream.callback.{callback}"

    return Subscriber(
        unique_id=unique_id,
        data_topic=data_topic,
        callback=callback,
        ioloop=ioloop,
        stage=stage,
        kind=kind,
        thread_name=thread_name,
    )


def describe(subscriber: Subscriber) -> Any:
    """Return a loggable description of a subscriber."""
    return subscriber.thread_name or subscriber.callback
