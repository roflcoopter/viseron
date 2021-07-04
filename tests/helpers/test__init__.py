"""Tests for helper module."""
import numpy as np

from viseron.helpers import generate_mask

from tests.const import MASK_ARRAY, MASK_COORDINATES


def test_generate_mask():
    """Test that mask is generated properly."""
    np.testing.assert_array_equal(
        generate_mask(MASK_COORDINATES),
        MASK_ARRAY,
    )
