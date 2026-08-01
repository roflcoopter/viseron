"""Verify the rootfs s6-overlay cont-init.d scripts populated container state."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import testinfra

ENV_FILES = (
    "VISERON_CONFIG_DIR",
    "VISERON_OPENCL_SUPPORTED",
    "VISERON_VAAPI_SUPPORTED",
    "VISERON_CUDA_SUPPORTED",
    "XDG_RUNTIME_DIR",
    "XDG_CURRENT_DESKTOP",
)


@pytest.mark.parametrize("env_var", ENV_FILES)
def test_environment_files_populated(host: testinfra.host.Host, env_var: str) -> None:
    """``/var/run/environment/<var>`` should exist and be non-empty."""
    path = f"/var/run/environment/{env_var}"
    file_ = host.file(path)
    assert file_.exists, f"{path} was not created by cont-init.d"
    content = file_.content_string.strip()
    assert content, f"{path} is empty"


def test_viseron_config_dir_value(host: testinfra.host.Host) -> None:
    """``VISERON_CONFIG_DIR`` should be ``/config`` for the smoke run."""
    file_ = host.file("/var/run/environment/VISERON_CONFIG_DIR")
    assert file_.exists
    assert file_.content_string.strip() == "/config"


@pytest.mark.parametrize(
    "env_var",
    [
        "VISERON_OPENCL_SUPPORTED",
        "VISERON_VAAPI_SUPPORTED",
        "VISERON_CUDA_SUPPORTED",
    ],
)
def test_capability_env_files_are_boolean(
    host: testinfra.host.Host, env_var: str
) -> None:
    """Capability detection scripts must write ``true`` or ``false``."""
    file_ = host.file(f"/var/run/environment/{env_var}")
    assert file_.exists
    value = file_.content_string.strip()
    assert value in {"true", "false"}, f"{env_var}={value!r} is not a boolean string"


def test_user_abc_present(host: testinfra.host.Host) -> None:
    """The ``abc`` user must exist with the correct uid.

    The ``video`` group is added dynamically by the container init scripts only
    if a render device is present, so we only check for membership in that group
    when /dev/dri exists.
    """
    user = host.user("abc")
    assert user.exists, "user 'abc' does not exist"
    assert user.uid == os.getuid(), (
        f"user 'abc' has uid {user.uid}, expected {os.getuid()}"
    )
    # Only assert the 'video' group when a render device was actually mounted
    # into the container
    if host.file("/dev/dri").exists:
        assert "video" in user.groups, f"abc not in 'video' group, got {user.groups}"


def test_postgres_ready(host: testinfra.host.Host) -> None:
    """``pg_isready`` should report the local postgres as accepting."""
    cmd = host.run("pg_isready -h /var/run/postgresql")
    assert cmd.rc == 0, (
        f"pg_isready failed: rc={cmd.rc}\nstdout=\n{cmd.stdout}\nstderr=\n{cmd.stderr}"
    )


def test_viseron_database_exists(host: testinfra.host.Host) -> None:
    """The ``viseron`` database should have been created by 80-postgres."""
    cmd = host.run(
        'su - postgres -c "psql -tAc \\"SELECT 1 FROM pg_database '
        "WHERE datname='viseron'\\\"\""
    )
    assert cmd.rc == 0, cmd.stderr
    assert cmd.stdout.strip() == "1", (
        f"viseron db not present:\nstdout=\n{cmd.stdout}\nstderr=\n{cmd.stderr}"
    )


def test_ffmpeg_wrapper_resolves(host: testinfra.host.Host) -> None:
    """``which ffmpeg`` (as the abc user) should resolve to the wrapper."""
    cmd = host.run("su - abc -c 'which ffmpeg'")
    assert cmd.rc == 0, cmd.stderr
    assert cmd.stdout.strip() == "/home/abc/bin/ffmpeg"


def test_gstreamer_inspect_runs(host: testinfra.host.Host) -> None:
    """``gst-inspect-1.0 --version`` should run and print a version."""
    cmd = host.run("gst-inspect-1.0 --version")
    output = cmd.stdout + cmd.stderr
    assert cmd.rc == 0, output
    assert "gst-inspect" in output.lower() or "gstreamer" in output.lower()
