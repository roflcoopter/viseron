"""Test the free-space eviction selection helper.

Pure-numpy, no database — exercises get_files_to_delete_for_free_space, which
decides the oldest set of files to delete to recover a free-space deficit.
"""

import numpy as np

from viseron.components.storage.check_tier import (
    FILES_DTYPE,
    get_files_to_delete_for_free_space,
)


def _make(rows):
    """Build a FILES_DTYPE array from (id, size, orig_ctime) triples."""
    return np.array(
        [(i, s, t, f"/tier/{i}.m4s", "/tier/") for (i, s, t) in rows],
        dtype=FILES_DTYPE,
    )


# Five files, 100 bytes each, one second apart. ids are intentionally out of
# chronological order to prove selection is by orig_ctime, not id or row order.
_DATA = _make(
    [
        (10, 100, 1000),  # oldest
        (40, 100, 1001),
        (20, 100, 1002),
        (50, 100, 1003),
        (30, 100, 1004),  # newest
    ]
)

# Everything old enough to be eligible unless a test says otherwise.
_ALL_ELIGIBLE = 2000.0


def test_no_deficit_is_noop() -> None:
    """A zero or negative deficit selects nothing."""
    assert get_files_to_delete_for_free_space(_DATA, 0, _ALL_ELIGIBLE).size == 0
    assert get_files_to_delete_for_free_space(_DATA, -50, _ALL_ELIGIBLE).size == 0


def test_empty_data_is_noop() -> None:
    """No candidate files selects nothing."""
    empty = np.empty(0, dtype=FILES_DTYPE)
    assert get_files_to_delete_for_free_space(empty, 100, _ALL_ELIGIBLE).size == 0


def test_selects_oldest_first_covering_deficit() -> None:
    """Smallest oldest-first prefix whose cumulative size covers the deficit."""
    result = get_files_to_delete_for_free_space(_DATA, 250, _ALL_ELIGIBLE)
    assert result["id"].tolist() == [10, 40, 20]


def test_exact_boundary_includes_covering_file() -> None:
    """A deficit landing exactly on a cumulative boundary stops there."""
    result = get_files_to_delete_for_free_space(_DATA, 200, _ALL_ELIGIBLE)
    assert result["id"].tolist() == [10, 40]


def test_deficit_larger_than_all_returns_all_oldest_first() -> None:
    """A deficit larger than everything selects every file, oldest first."""
    result = get_files_to_delete_for_free_space(_DATA, 10_000, _ALL_ELIGIBLE)
    assert result["id"].tolist() == [10, 40, 20, 50, 30]


def test_min_age_protects_recent_files() -> None:
    """Files newer than the cutoff are never eligible for eviction."""
    # Only files with orig_ctime <= 1001 are eligible (ids 10 and 40).
    result = get_files_to_delete_for_free_space(_DATA, 500, 1001.0)
    assert result["id"].tolist() == [10, 40]


def test_all_files_too_recent_is_noop() -> None:
    """When every file is within the protection window, nothing is selected."""
    result = get_files_to_delete_for_free_space(_DATA, 500, 500.0)
    assert result.size == 0
