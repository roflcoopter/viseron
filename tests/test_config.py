"""Test config loading functionality."""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from viseron.config import create_default_config, load_config, load_secrets


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
