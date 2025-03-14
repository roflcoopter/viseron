"""Manager for communication between python shells."""
from collections.abc import Callable
from multiprocessing.managers import (  # type: ignore
    BaseManager,
    dispatch,
    listener_client,
)
from queue import Queue


class QueueManager(BaseManager):
    """BaseManager class for queue manager."""

    get_process_queue: Callable[..., Queue]
    get_output_queue: Callable[..., Queue]


def start(
    address: str, port: int, authkey: str, process_queue: Queue, output_queue: Queue
) -> QueueManager:
    """Serve manager."""
    # Set up queues
    QueueManager.register("get_process_queue", callable=lambda: process_queue)
    QueueManager.register("get_output_queue", callable=lambda: output_queue)

    # Start server
    manager = QueueManager(address=(address, port), authkey=authkey.encode("utf-8"))
    return manager


def stop(address: str, port: int, authkey: str) -> None:
    """Shutdown manager."""
    client = listener_client["pickle"][1]
    # address and authkey same as when started the manager
    conn = client(address=(address, port), authkey=authkey.encode("utf-8"))
    dispatch(conn, None, "shutdown")
    conn.close()


def connect(address: str, port: int, authkey: str) -> tuple[Queue, Queue]:
    """Connect to manager."""
    # Connect to server
    QueueManager.register("get_process_queue")
    QueueManager.register("get_output_queue")
    manager = QueueManager(address=(address, port), authkey=authkey.encode("utf-8"))
    manager.connect()

    # Set up queues
    process_queue = manager.get_process_queue()
    output_queue = manager.get_output_queue()
    return process_queue, output_queue
