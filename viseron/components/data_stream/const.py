"""data_stream constants."""

from __future__ import annotations

from typing import Final

COMPONENT: Final = "data_stream"

# Absorbs publisher bursts. Drained as fast as subscriber lookup allows.
DATA_QUEUE_MAXSIZE: Final = 10000

# Per subscriber backlog. A full queue drops its oldest instead of stalling the bus.
SUBSCRIBER_QUEUE_MAXSIZE: Final = 1000

# Shared by callback subscribers, sized for I/O bound work.
CALLBACK_WORKERS: Final = 32

# Signal topics bypass the bounded data queue so shutdown can never be dropped.
SIGNAL_TOPIC_PREFIX: Final = "viseron/signal/"

# Cleared past this size since wildcard patterns are user supplied.
MATCH_CACHE_MAXSIZE: Final = 4096

DROP_WARNING_INTERVAL: Final = 10.0

# Publishing gives up after this many attempts to make room in a full queue.
PUBLISH_MAX_ATTEMPTS: Final = 10
