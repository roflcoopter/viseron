"""Test the FixedSizeDict class."""
from viseron.helpers.fixed_size_dict import FixedSizeDict


class TestFixedSizeDict:
    """Test the FixedSizeDict class."""

    def test_maxlen(self):
        """Test that the dictionary does not exceed the maximum size."""
        test: FixedSizeDict[str, int] = FixedSizeDict(maxlen=2)
        test["a"] = 1
        test["b"] = 2
        test["c"] = 3
        assert len(test) == 2
        assert "a" not in test
        assert test["b"] == 2
        assert test["c"] == 3

    def test_get(self):
        """Test that the get method moves the item to the end."""
        test: FixedSizeDict[str, int] = FixedSizeDict(maxlen=2)
        test["a"] = 1
        test["b"] = 2
        test.get("a")
        test["c"] = 3
        assert len(test) == 2
        assert "b" not in test
        assert test["a"] == 1
        assert test["c"] == 3

    def test_no_maxlen(self):
        """Test that the dictionary works with no maximum size."""
        # Test that the dictionary works with a maxlen of 0 (unlimited size)
        test: FixedSizeDict[str, int] = FixedSizeDict(maxlen=0)
        for i in range(100):
            test[i] = i
        assert len(test) == 100
        for i in range(100):
            assert test[i] == i

        # Test that the dictionary works with no maxlen specified (unlimited size)
        test = FixedSizeDict()
        for i in range(100):
            test[i] = i
        assert len(test) == 100
        for i in range(100):
            assert test[i] == i
