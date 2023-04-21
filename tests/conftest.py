"""Viseron fixtures."""
from typing import Iterator
from unittest.mock import MagicMock, patch

import pytest

from viseron import Viseron
from viseron.components.data_stream import COMPONENT as DATA_STREAM, DataStream


@pytest.fixture
def vis():
    """Fixture to test Viseron instance."""
    viseron = Viseron()
    viseron.data[DATA_STREAM] = MagicMock(spec=DataStream)
    return viseron


@pytest.fixture(scope="session", autouse=True)
def patch_enable_logging() -> Iterator[None]:
    """Patch enable_logging to avoid adding duplicate handlers."""
    with patch("viseron.enable_logging"):
        yield
