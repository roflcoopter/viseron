"""Verify the Python environment inside the image."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import testinfra

PYTHON_IMPORTS = (
    "cv2",
    "numpy",
    "sqlalchemy",
    "alembic",
    "viseron",
    "viseron.components",
    "viseron.components.webserver",
    "viseron.components.storage",
    "tornado",
    "voluptuous",
    "ruamel.yaml",
    "hailo_platform",
)

# Modules that are not packaged for certain architectures.
# Tests for these modules are skipped on the listed architectures.
_ARCH_EXCLUDED_IMPORTS: dict[str, set[str]] = {
    # hailo_platform is only provided for amd64 and aarch64.
    "rpi3": {"hailo_platform"},
}


@pytest.mark.parametrize("module", PYTHON_IMPORTS)
def test_python_module_imports(
    host: testinfra.host.Host, module: str, arch: str
) -> None:
    """Each module must import without raising."""
    if module in _ARCH_EXCLUDED_IMPORTS.get(arch, set()):
        pytest.skip(f"{module} is not available on {arch}")
    cmd = host.run(f"python3 -c 'import {module}'")
    assert cmd.rc == 0, (
        f"failed to import {module}:\nstdout=\n{cmd.stdout}\nstderr=\n{cmd.stderr}"
    )


def test_cv2_version_matches_env(host: testinfra.host.Host, expected_versions) -> None:
    """``cv2.__version__`` should match ``OPENCV_VERSION`` from .env."""
    expected = expected_versions.get("OPENCV_VERSION")
    assert expected, "OPENCV_VERSION missing from azure-pipelines/.env"
    cmd = host.run("python3 -c 'import cv2; print(cv2.__version__)'")
    assert cmd.rc == 0, cmd.stderr
    assert cmd.stdout.strip() == expected, (
        f"cv2.__version__={cmd.stdout.strip()!r} expected {expected!r}"
    )


def test_cv2_built_without_ffmpeg(host: testinfra.host.Host) -> None:
    """``cv2.getBuildInformation()`` should report FFMPEG: NO."""
    cmd = host.run("python3 -c 'import cv2; print(cv2.getBuildInformation())'")
    assert cmd.rc == 0, cmd.stderr
    assert "FFMPEG" in cmd.stdout
    ffmpeg_lines = [
        line for line in cmd.stdout.splitlines() if "FFMPEG" in line and ":" in line
    ]
    assert ffmpeg_lines, "FFMPEG section not found in cv2 build info"
    assert any("NO" in line for line in ffmpeg_lines), (
        "FFMPEG enabled in cv2 build info:\n" + "\n".join(ffmpeg_lines)
    )


def test_viseron_metadata(host: testinfra.host.Host) -> None:
    """``viseron`` must expose its version and basic component module."""
    cmd = host.run(
        'python3 -c "'
        "import json, viseron; "
        "print(json.dumps({'version': getattr(viseron, '__version__', None), "
        "'has_components': hasattr(viseron, 'components')}))\""
    )
    assert cmd.rc == 0, cmd.stderr
    payload = json.loads(cmd.stdout.strip())
    assert payload["has_components"] is True
