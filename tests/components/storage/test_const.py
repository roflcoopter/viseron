"""Tests for the storage component constants."""

from __future__ import annotations

import pytest

from viseron.components.storage.const import _database_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        pytest.param(
            "postgresql://postgres@localhost/viseron",
            "postgresql+psycopg2://postgres@localhost/viseron",
            id="default",
        ),
        pytest.param(
            "postgresql://viseron:p%40ss@db:5432/viseron",
            "postgresql+psycopg2://viseron:p%40ss@db:5432/viseron",
            id="password_kept",
        ),
        pytest.param(
            "postgresql+psycopg2://postgres@localhost/viseron",
            "postgresql+psycopg2://postgres@localhost/viseron",
            id="psycopg2_unchanged",
        ),
        pytest.param(
            "postgresql+psycopg://postgres@localhost/viseron",
            "postgresql+psycopg://postgres@localhost/viseron",
            id="explicit_driver_unchanged",
        ),
    ],
)
def test_database_url(url: str, expected: str) -> None:
    """Plain postgresql:// URLs are pinned to psycopg2, explicit drivers kept."""
    assert _database_url(url) == expected
