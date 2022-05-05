"""Viseron fixtures."""
import pytest

from viseron import Viseron


@pytest.fixture
def vis():
    """Fixture to test Viseron instance."""
    return Viseron()
