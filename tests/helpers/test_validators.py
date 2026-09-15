"""Tests for viseron.helpers.validators."""

import pytest
import voluptuous as vol

from viseron.helpers.validators import (
    UNDEFINED,
    CoerceNoneToDict,
    Maybe,
    Slug,
    StringKey,
    Timezone,
)


class TestStringKey:
    """Tests for the StringKey validator."""

    def test_returns_value_for_string(self):
        """Test that StringKey returns the value when given a string."""
        validator = StringKey(description="Test header")
        assert validator("Content-Type") == "Content-Type"
        assert validator("Authorization") == "Authorization"
        assert validator("X-Custom-Header") == "X-Custom-Header"
        assert validator("") == ""

    def test_raises_invalid_for_non_string(self):
        """Test that StringKey raises vol.Invalid for non-string values."""
        validator = StringKey(description="Test header")
        with pytest.raises(vol.Invalid):
            validator(123)
        with pytest.raises(vol.Invalid):
            validator(None)
        with pytest.raises(vol.Invalid):
            validator([1, 2, 3])
        with pytest.raises(vol.Invalid):
            validator({"key": "value"})
        with pytest.raises(vol.Invalid):
            validator(True)  # noqa: FBT003

    def test_used_as_dict_key_in_schema(self):
        """Test that StringKey works as a dictionary key validator in a schema.

        This simulates how it's used in the webhook component schema.
        When used as a dict key validator, voluptuous calls it and uses
        the return value as the key. If StringKey returns None (the bug),
        all keys become 'None'.
        """
        schema = vol.Schema({StringKey(description="Test"): str})
        result = schema({"Content-Type": "application/json"})
        assert result == {"Content-Type": "application/json"}
        assert next(iter(result.keys())) == "Content-Type"
        assert next(iter(result.keys())) != "None"


class TestCoerceNoneToDict:
    """Tests for the CoerceNoneToDict validator."""

    def test_coerces_none_to_dict(self):
        """Test that None is coerced to an empty dict."""
        validator = CoerceNoneToDict()
        assert validator(None) == {}

    def test_returns_dict_as_is(self):
        """Test that a dict is returned as-is."""
        validator = CoerceNoneToDict()
        assert validator(
            {"key": "value"}  # type: ignore[dict-item]
        ) == {"key": "value"}

    def test_raises_for_non_dict_non_none(self):
        """Test that non-dict, non-None values raise CoerceInvalid."""
        validator = CoerceNoneToDict()
        with pytest.raises(vol.CoerceInvalid):
            validator("string")  # type: ignore[arg-type]
        with pytest.raises(vol.CoerceInvalid):
            validator(123)  # type: ignore[arg-type]


class TestSlug:
    """Tests for the Slug validator."""

    def test_returns_value_for_valid_slug(self):
        """Test that a valid slug is returned."""
        validator = Slug()
        assert validator("valid_slug") == "valid_slug"
        assert validator("test") == "test"
        assert validator("abc123") == "abc123"

    def test_raises_for_invalid_slug(self):
        """Test that an invalid slug raises vol.Invalid."""
        validator = Slug()
        with pytest.raises(vol.Invalid):
            validator("INVALID")
        with pytest.raises(vol.Invalid):
            validator("has spaces")
        with pytest.raises(vol.Invalid):
            validator(123)
        with pytest.raises(vol.Invalid):
            validator(None)


class TestTimezone:
    """Tests for the Timezone validator."""

    def test_returns_value_for_valid_iana_timezone(self):
        """Test that a valid IANA timezone name is returned unchanged."""
        validator = Timezone()
        assert validator("Europe/Stockholm") == "Europe/Stockholm"
        assert validator("UTC") == "UTC"

    def test_raises_for_unknown_timezone(self):
        """Test that an unknown timezone name raises vol.Invalid."""
        validator = Timezone()
        with pytest.raises(vol.Invalid):
            validator("Not/AZone")

    def test_raises_for_non_string(self):
        """Test that a non-string value raises vol.Invalid."""
        validator = Timezone()
        with pytest.raises(vol.Invalid):
            validator(123)
        with pytest.raises(vol.Invalid):
            validator(None)

    def test_passes_undefined_through_without_logging(
        self, caplog: pytest.LogCaptureFixture
    ):
        """Test that the UNDEFINED sentinel is passed through untouched.

        Maybe(Timezone()) runs the UNDEFINED schema default through this
        validator before reaching the UNDEFINED branch of vol.Any. Rejecting
        it would log a bogus error on every config load for anyone who has a
        schedule but no explicit timezone.
        """
        validator = Timezone()
        assert validator(UNDEFINED) is UNDEFINED
        instance = UNDEFINED()
        assert validator(instance) is instance
        assert "Invalid timezone" not in caplog.text

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "/etc/passwd",
            "../../etc/passwd",
            "Europe/../Europe/Berlin",
        ],
    )
    def test_raises_invalid_for_malformed_keys(self, value: str):
        """Test that malformed zone keys raise vol.Invalid, not ValueError."""
        validator = Timezone()
        with pytest.raises(vol.Invalid):
            validator(value)


class TestMaybe:
    """Tests for the Maybe validator."""

    def test_allows_valid_value(self):
        """Test that a valid value passes through."""
        validator = Maybe(int)
        assert validator(5) == 5

    def test_allows_none(self):
        """Test that None is allowed."""
        validator = Maybe(int)
        assert validator(None) is None

    def test_rejects_invalid_type(self):
        """Test that an invalid type raises vol.Invalid."""
        validator = Maybe(int)
        with pytest.raises(vol.Invalid):
            validator("not_an_int")
