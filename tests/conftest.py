"""Viseron fixtures."""
from typing import Iterator
from unittest.mock import patch

import pytest

from viseron import Viseron


@pytest.fixture
def vis():
    """Fixture to test Viseron instance."""
    return Viseron()


@pytest.fixture(scope="session", autouse=True)
def patch_enable_logging() -> Iterator[None]:
    """Patch enable_logging to avoid adding duplicate handlers."""
    with patch("viseron.enable_logging"):
        yield
