"""Test config loading functionality."""
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from viseron.config import (
    IdentifierChange,
    create_default_config,
    diff_identifier_config,
    load_config,
    load_secrets,
)


class TestLoadSecrets:
    """Test load_secrets function."""

    def test_load_secrets_success(self):
        """Test loading secrets from a valid secrets.yaml file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as temp_file:
            temp_file.write("my_secret: secret_value\n")
            temp_file.write("another_secret: another_value\n")
            temp_file.flush()

            with patch("viseron.config.SECRETS_PATH", temp_file.name):
                secrets = load_secrets()

            Path(temp_file.name).unlink()

        assert secrets == {
            "my_secret": "secret_value",
            "another_secret": "another_value",
        }

    def test_load_secrets_file_not_found(self):
        """Test loading secrets when file doesn't exist."""
        with patch("viseron.config.SECRETS_PATH", "/nonexistent/path/secrets.yaml"):
            secrets = load_secrets()

        assert secrets is None

    def test_load_secrets_empty_file(self):
        """Test loading secrets from an empty file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as temp_file:
            temp_file.flush()

            with patch("viseron.config.SECRETS_PATH", temp_file.name):
                secrets = load_secrets()

            Path(temp_file.name).unlink()

        assert secrets is None


class TestLoadConfig:
    """Test load_config function."""

    def test_load_config_basic(self):
        """Test loading a basic config.yaml file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as temp_file:
            temp_file.write("component1:\n")
            temp_file.write("  setting1: value1\n")
            temp_file.write("component2:\n")
            temp_file.write("  setting2: value2\n")
            temp_file.flush()

            with patch("viseron.config.CONFIG_PATH", temp_file.name):
                config = load_config(create_default=False)

            Path(temp_file.name).unlink()

        assert config == {
            "component1": {"setting1": "value1"},
            "component2": {"setting2": "value2"},
        }

    def test_load_config_with_secret(self):
        """Test loading config with !secret tag."""
        with (
            tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as secrets_file,
            tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as config_file,
        ):
            # Create secrets file
            secrets_file.write("my_password: supersecret123\n")
            secrets_file.flush()

            # Create config file with !secret tag
            config_file.write("database:\n")
            config_file.write("  password: !secret my_password\n")
            config_file.flush()

            with (
                patch("viseron.config.SECRETS_PATH", secrets_file.name),
                patch("viseron.config.CONFIG_PATH", config_file.name),
            ):
                config = load_config(create_default=False)

            Path(secrets_file.name).unlink()
            Path(config_file.name).unlink()

        assert config == {"database": {"password": "supersecret123"}}

    def test_load_config_secret_not_found(self):
        """Test loading config when secret doesn't exist in secrets.yaml."""
        with (
            tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as secrets_file,
            tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as config_file,
        ):
            # Create secrets file
            secrets_file.write("existing_secret: value\n")
            secrets_file.flush()

            # Create config file with !secret tag for non-existent secret
            config_file.write("database:\n")
            config_file.write("  password: !secret nonexistent_secret\n")
            config_file.flush()

            with (
                patch("viseron.config.SECRETS_PATH", secrets_file.name),
                patch("viseron.config.CONFIG_PATH", config_file.name),
            ):
                with pytest.raises(
                    ValueError,
                    match="secret nonexistent_secret does not exist in secrets.yaml",
                ):
                    load_config(create_default=False)

            Path(secrets_file.name).unlink()
            Path(config_file.name).unlink()

    def test_load_config_secret_without_secrets_file(self):
        """Test loading config with !secret when secrets.yaml doesn't exist."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as config_file:
            # Create config file with !secret tag
            config_file.write("database:\n")
            config_file.write("  password: !secret my_password\n")
            config_file.flush()

            with (
                patch("viseron.config.SECRETS_PATH", "/nonexistent/secrets.yaml"),
                patch("viseron.config.CONFIG_PATH", config_file.name),
            ):
                with pytest.raises(
                    ValueError,
                    match="!secret found in config.yaml, but no secrets.yaml exists",
                ):
                    load_config(create_default=False)

            Path(config_file.name).unlink()

    def test_load_config_empty_file(self):
        """Test loading an empty config file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as temp_file:
            temp_file.flush()

            with patch("viseron.config.CONFIG_PATH", temp_file.name):
                config = load_config(create_default=False)

            Path(temp_file.name).unlink()

        assert config == {}

    def test_load_config_none_values(self):
        """Test that None values are converted to empty dicts."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as temp_file:
            temp_file.write("component1:\n")
            temp_file.write("component2: null\n")
            temp_file.write("component3:\n")
            temp_file.write("  setting: value\n")
            temp_file.flush()

            with patch("viseron.config.CONFIG_PATH", temp_file.name):
                config = load_config(create_default=False)

            Path(temp_file.name).unlink()

        assert config == {
            "component1": {},
            "component2": {},
            "component3": {"setting": "value"},
        }

    def test_load_config_complex_types(self):
        """Test loading config with various YAML types."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as temp_file:
            temp_file.write("component:\n")
            temp_file.write("  string: hello\n")
            temp_file.write("  number: 42\n")
            temp_file.write("  float: 3.14\n")
            temp_file.write("  boolean: true\n")
            temp_file.write("  list:\n")
            temp_file.write("    - item1\n")
            temp_file.write("    - item2\n")
            temp_file.write("  nested:\n")
            temp_file.write("    key: value\n")
            temp_file.flush()

            with patch("viseron.config.CONFIG_PATH", temp_file.name):
                config = load_config(create_default=False)

            Path(temp_file.name).unlink()

        assert config == {
            "component": {
                "string": "hello",
                "number": 42,
                "float": 3.14,
                "boolean": True,
                "list": ["item1", "item2"],
                "nested": {"key": "value"},
            }
        }


class TestCreateDefaultConfig:
    """Test create_default_config function."""

    def test_create_default_config_success(self):
        """Test creating default config file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            result = create_default_config(str(config_path))

            assert result is True
            assert config_path.exists()

    def test_create_default_config_failure(self):
        """Test creating default config in invalid path."""
        result = create_default_config("/invalid/nonexistent/path/config.yaml")
        assert result is False


class TestIdentifierChange:
    """Test IdentifierChange dataclass."""

    def test_identifier_added(self) -> None:
        """Test that is_added returns True when old_config is None."""
        change = IdentifierChange(
            component_name="ffmpeg",
            domain="camera",
            identifier="cam1",
            old_config=None,
            new_config={"host": "192.168.1.1"},
        )
        assert change.is_added is True
        assert change.is_removed is False
        assert change.is_identifier_level_change is True

    def test_identifier_removed(self) -> None:
        """Test that is_removed returns True when new_config is None."""
        change = IdentifierChange(
            component_name="ffmpeg",
            domain="camera",
            identifier="cam1",
            old_config={"host": "192.168.1.1"},
            new_config=None,
        )
        assert change.is_removed is True
        assert change.is_added is False
        assert change.is_identifier_level_change is True

    def test_identifier_not_added_or_removed_when_both_present(self) -> None:
        """Test that neither is_added nor is_removed when both configs present."""
        change = IdentifierChange(
            component_name="darknet",
            domain="object_detector",
            identifier="cam1",
            old_config={"threshold": 0.5},
            new_config={"threshold": 0.8},
        )
        assert change.is_added is False
        assert change.is_removed is False
        assert change.is_identifier_level_change is True

    def test_identifier_not_added_or_removed_when_both_none(self) -> None:
        """Test that neither is_added nor is_removed when both configs are None."""
        change = IdentifierChange(
            component_name="ffmpeg",
            domain="camera",
            identifier="cam1",
            old_config=None,
            new_config=None,
        )
        assert change.is_added is False
        assert change.is_removed is False
        assert change.is_identifier_level_change is False

    def test_is_identifier_level_change_no_change(self) -> None:
        """Test is_identifier_level_change returns False when configs are equal."""
        config = {"threshold": 0.5, "labels": ["person", "car"]}
        change = IdentifierChange(
            component_name="darknet",
            domain="object_detector",
            identifier="cam1",
            old_config=config.copy(),
            new_config=config.copy(),
        )
        assert change.is_identifier_level_change is False

    def test_is_identifier_level_change_both_empty(self) -> None:
        """Test is_identifier_level_change returns False when both configs are empty."""
        change = IdentifierChange(
            component_name="ffmpeg",
            domain="camera",
            identifier="cam1",
            old_config={},
            new_config={},
        )
        assert change.is_identifier_level_change is False


class TestDiffIdentifierConfig:
    """Test diff_identifier_config function."""

    def test_no_changes(self) -> None:
        """Test diff when old and new configs are identical."""
        config: dict[str, Any] = {
            "cam1": {"host": "192.168.1.1"},
            "cam2": {"host": "192.168.1.2"},
        }
        result = diff_identifier_config("ffmpeg", "camera", config, config.copy())
        assert not result

    def test_identifier_added(self) -> None:
        """Test diff detects a newly added identifier."""
        old_config: dict[str, Any] = {"cam1": {"host": "192.168.1.1"}}
        new_config: dict[str, Any] = {
            "cam1": {"host": "192.168.1.1"},
            "cam2": {"host": "192.168.1.2"},
        }
        result = diff_identifier_config("ffmpeg", "camera", old_config, new_config)
        assert len(result) == 1
        assert result[0].identifier == "cam2"
        assert result[0].is_added is True
        assert result[0].new_config == {"host": "192.168.1.2"}
        assert result[0].old_config is None

    def test_identifier_removed(self) -> None:
        """Test diff detects a removed identifier."""
        old_config: dict[str, Any] = {
            "cam1": {"host": "192.168.1.1"},
            "cam2": {"host": "192.168.1.2"},
        }
        new_config: dict[str, Any] = {"cam1": {"host": "192.168.1.1"}}
        result = diff_identifier_config("ffmpeg", "camera", old_config, new_config)
        assert len(result) == 1
        assert result[0].identifier == "cam2"
        assert result[0].is_removed is True
        assert result[0].old_config == {"host": "192.168.1.2"}
        assert result[0].new_config is None

    def test_identifier_modified(self) -> None:
        """Test diff detects a modified identifier."""
        old_config: dict[str, Any] = {"cam1": {"host": "192.168.1.1"}}
        new_config: dict[str, Any] = {"cam1": {"host": "10.0.0.1"}}
        result = diff_identifier_config("ffmpeg", "camera", old_config, new_config)
        assert len(result) == 1
        assert result[0].identifier == "cam1"
        assert result[0].is_added is False
        assert result[0].is_removed is False
        assert result[0].is_identifier_level_change is True
        assert result[0].old_config == {"host": "192.168.1.1"}
        assert result[0].new_config == {"host": "10.0.0.1"}

    def test_multiple_changes(self) -> None:
        """Test diff detects added, removed, and modified identifiers at once."""
        old_config: dict[str, Any] = {
            "cam1": {"host": "192.168.1.1"},
            "cam2": {"host": "192.168.1.2"},
        }
        new_config: dict[str, Any] = {
            "cam1": {"host": "10.0.0.1"},
            "cam3": {"host": "192.168.1.3"},
        }
        result = diff_identifier_config("ffmpeg", "camera", old_config, new_config)
        changes_by_id = {c.identifier: c for c in result}

        assert len(result) == 3
        assert changes_by_id["cam1"].is_identifier_level_change is True
        assert changes_by_id["cam2"].is_removed is True
        assert changes_by_id["cam3"].is_added is True

    def test_both_empty(self) -> None:
        """Test diff with empty old and new configs."""
        result = diff_identifier_config("ffmpeg", "camera", {}, {})
        assert not result

    def test_all_added(self) -> None:
        """Test diff when going from empty to populated config."""
        new_config: dict[str, Any] = {
            "cam1": {"host": "192.168.1.1"},
            "cam2": {"host": "192.168.1.2"},
        }
        result = diff_identifier_config("ffmpeg", "camera", {}, new_config)
        assert len(result) == 2
        assert all(c.is_added for c in result)

    def test_all_removed(self) -> None:
        """Test diff when going from populated to empty config."""
        old_config: dict[str, Any] = {
            "cam1": {"host": "192.168.1.1"},
            "cam2": {"host": "192.168.1.2"},
        }
        result = diff_identifier_config("ffmpeg", "camera", old_config, {})
        assert len(result) == 2
        assert all(c.is_removed for c in result)

    def test_deep_copies_configs(self) -> None:
        """Test that diff_identifier_config deep copies config values."""
        old_config: dict[str, Any] = {"cam1": {"host": "192.168.1.1"}}
        new_config: dict[str, Any] = {"cam2": {"host": "192.168.1.2"}}
        result = diff_identifier_config("ffmpeg", "camera", old_config, new_config)
        changes_by_id = {c.identifier: c for c in result}

        # Mutating original dicts should not affect the change objects
        old_config["cam1"]["host"] = "MUTATED"
        new_config["cam2"]["host"] = "MUTATED"
        assert changes_by_id["cam1"].old_config == {"host": "192.168.1.1"}
        assert changes_by_id["cam2"].new_config == {"host": "192.168.1.2"}

    def test_unchanged_identifiers_not_included(self) -> None:
        """Test that identifiers with no changes are excluded from the result."""
        old_config: dict[str, Any] = {
            "cam1": {"host": "192.168.1.1"},
            "cam2": {"host": "192.168.1.2"},
        }
        new_config: dict[str, Any] = {
            "cam1": {"host": "192.168.1.1"},
            "cam2": {"host": "10.0.0.2"},
        }
        result = diff_identifier_config("ffmpeg", "camera", old_config, new_config)
        assert len(result) == 1
        assert result[0].identifier == "cam2"
