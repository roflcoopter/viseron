"""Tests for viseron.helpers.schemas."""

import pytest
import voluptuous as vol

from viseron.helpers.schemas import FLOAT_POSITIVE


@pytest.mark.parametrize("value", [0, 0.0, "0", -1, -0.5])
def test_float_positive_rejects_zero_and_negatives(value):
    """Test that zero and negative values raise vol.Invalid."""
    with pytest.raises(vol.Invalid):
        FLOAT_POSITIVE(value)


def test_float_positive_accepts_positive_values():
    """Test that positive values, including fractions, pass through as float."""
    assert FLOAT_POSITIVE(0.5) == 0.5
    assert FLOAT_POSITIVE("2") == 2.0
    assert FLOAT_POSITIVE(1) == 1.0
