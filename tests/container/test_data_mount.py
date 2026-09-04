"""Smoke tests for the single /data volume mount path (Home Assistant add-on mode).

When the container is started with a /data directory present instead of individual
storage directories, the 10-adduser init script must:
  - create /data/{folder} subdirectories
  - create /{folder} -> /data/{folder} symlinks
  - allow Viseron to boot normally through those symlinks
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import testinfra

from . import _helpers as helpers
from .conftest import (
    _MINIMAL_CONFIG,
    NGINX_PORT,
    READY_LOG_PATTERN,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    import docker

# Folders that 10-adduser symlinks when /data exists.
# Must match the `for folder in ...` loop in rootfs/etc/cont-init.d/10-adduser.
DATA_SYMLINKED_FOLDERS = ("event_clips", "segments", "snapshots", "thumbnails")

# Patterns that indicate a fatal error in boot logs (mirrors test_viseron_app.py).
_FATAL_LOG_PATTERNS = (
    re.compile(r"^Traceback \(most recent call last\):", re.MULTILINE),
    re.compile(r"\b(viseron(\.[\w\.]+)?)\b\s+ERROR\b", re.IGNORECASE | re.MULTILINE),
)


def _data_mount_container(
    docker_client: docker.DockerClient,
    image: str,
    docker_platform: str,
    boot_timeout: float,
    artifact_dir: Path,
    request: pytest.FixtureRequest,
    *,
    name_suffix: str,
    env_overrides: dict[str, str] | None = None,
    publish_nginx: bool = False,
    log_label: str,
    config_owner: tuple[int, int] | None = None,
) -> Iterator[Any]:
    """Start and manage the lifecycle for a /data-mount smoke-test container.

    ``config_owner``, if given, seeds ``/config`` as already owned by that
    ``(uid, gid)`` instead of root. This simulates a host bind mount whose
    ownership is already correct, which is a precondition for
    ``VISERON_DISABLE_CHOWN`` (documented in installation.mdx) since that
    flag skips the container's own recursive chown of ``/config``.
    """
    container_name = helpers.unique_container_name(
        f"viseron-smoke-data-mount-{name_suffix}"
    )

    environment = {
        "PUID": str(os.getuid()),
        "PGID": str(os.getgid()),
        "TZ": "UTC",
    }
    if env_overrides:
        environment.update(env_overrides)

    run_kwargs: dict[str, Any] = {
        "image": image,
        "name": container_name,
        "environment": environment,
    }
    if publish_nginx:
        run_kwargs["ports"] = {f"{NGINX_PORT}/tcp": None}

    if Path("/dev/dri").exists():
        run_kwargs["devices"] = ["/dev/dri:/dev/dri"]
    if docker_platform:
        run_kwargs["platform"] = docker_platform

    print(  # noqa: T201
        f"\n[smoke] starting {log_label} container {container_name} from {image} "
        f"(platform={docker_platform or 'default'})"
    )
    try:
        container = docker_client.containers.create(**run_kwargs)
    except Exception as exc:
        (artifact_dir / f"{container_name}-startup-error.txt").write_text(
            f"Container failed to create:\n{exc}\n", encoding="utf-8"
        )
        raise

    # Seed /config and ONLY /data, no individual storage dirs.
    # The 10-adduser init script will create /data/{folder} and symlinks.
    helpers.put_abs(
        container,
        "/config/config.yaml",
        _MINIMAL_CONFIG.read_bytes(),
        owner=config_owner,
    )
    helpers.create_directories(container, "/data")
    helpers.install_http_probe(container)

    try:
        container.start()
    except Exception as exc:
        (artifact_dir / f"{container_name}-startup-error.txt").write_text(
            f"Container failed to start:\n{exc}\n", encoding="utf-8"
        )
        container.remove(force=True)
        raise

    def _dump_artifacts() -> None:
        try:
            (artifact_dir / f"{container_name}.log").write_bytes(
                container.logs(stdout=True, stderr=True)
            )
        except Exception as exc:  # pylint: disable=broad-except # noqa: BLE001
            print(f"[smoke] could not capture {log_label} logs: {exc}")  # noqa: T201
        print(f"[smoke] artifacts saved to {artifact_dir}")  # noqa: T201

    try:
        helpers.wait_for_log(container, READY_LOG_PATTERN, timeout=boot_timeout)
    except BaseException:
        _dump_artifacts()
        try:
            container.stop(timeout=10)
        finally:
            container.remove(force=True)
        raise

    yield container

    if request.session.testsfailed:
        _dump_artifacts()

    if request.config.getoption("--keep-container"):
        print(  # noqa: T201
            f"[smoke] --keep-container set; leaving {container_name} running"
        )
        return

    try:
        container.stop(timeout=15)
    finally:
        container.remove(force=True)


@pytest.fixture(scope="session")
def viseron_container_data_mount(
    docker_client: docker.DockerClient,
    image: str,
    docker_platform: str,
    boot_timeout: float,
    artifact_dir: Path,
    request: pytest.FixtureRequest,
) -> Iterator[Any]:
    """Start a /data-mount container with default chown behavior."""
    yield from _data_mount_container(
        docker_client,
        image,
        docker_platform,
        boot_timeout,
        artifact_dir,
        request,
        name_suffix="default",
        publish_nginx=True,
        log_label="data-mount",
    )


@pytest.fixture(scope="session")
def viseron_container_data_mount_disable_chown(
    docker_client: docker.DockerClient,
    image: str,
    docker_platform: str,
    boot_timeout: float,
    artifact_dir: Path,
    request: pytest.FixtureRequest,
) -> Iterator[Any]:
    """Start a /data-mount container with VISERON_DISABLE_CHOWN enabled.

    /config is pre-seeded as owned by the PUID/PGID the container will run
    with, since VISERON_DISABLE_CHOWN skips the recursive chown that would
    otherwise fix up ownership at boot (see installation.mdx: "ownership of
    your mounted paths must already be correct on the host").
    """
    yield from _data_mount_container(
        docker_client,
        image,
        docker_platform,
        boot_timeout,
        artifact_dir,
        request,
        name_suffix="no-chown",
        env_overrides={"VISERON_DISABLE_CHOWN": "true"},
        log_label="no-chown",
        config_owner=(os.getuid(), os.getgid()),
    )


@pytest.fixture(scope="session")
def host_data_mount(viseron_container_data_mount: Any) -> testinfra.host.Host:
    """Return a testinfra host bound to the data-mount container."""
    return testinfra.get_host(f"docker://{viseron_container_data_mount.name}")


@pytest.fixture(scope="session")
def webserver_url_data_mount(viseron_container_data_mount: Any) -> str:
    """Return the nginx URL inside the data-mount container."""
    _ = viseron_container_data_mount
    return f"http://127.0.0.1:{NGINX_PORT}"


@pytest.fixture(scope="session")
def boot_logs_data_mount(viseron_container_data_mount: Any) -> str:
    """Return the captured boot logs from the data-mount container."""
    return viseron_container_data_mount.logs().decode("utf-8", errors="replace")


@pytest.fixture(scope="session")
def host_data_mount_disable_chown(
    viseron_container_data_mount_disable_chown: Any,
) -> testinfra.host.Host:
    """Return a testinfra host for the no-chown data-mount container."""
    return testinfra.get_host(
        f"docker://{viseron_container_data_mount_disable_chown.name}"
    )


@pytest.fixture(scope="session")
def boot_logs_data_mount_disable_chown(
    viseron_container_data_mount_disable_chown: Any,
) -> str:
    """Return the captured boot logs from the no-chown data-mount container."""
    return viseron_container_data_mount_disable_chown.logs().decode(
        "utf-8", errors="replace"
    )


@pytest.mark.parametrize("folder", DATA_SYMLINKED_FOLDERS)
def test_data_subdir_created(host_data_mount: testinfra.host.Host, folder: str) -> None:
    """/data/{folder} must be created as a real directory by the init script."""
    path = f"/data/{folder}"
    f = host_data_mount.file(path)
    assert f.exists, f"{path} was not created under /data"
    assert f.is_directory, f"{path} exists but is not a directory"


@pytest.mark.parametrize("folder", DATA_SYMLINKED_FOLDERS)
def test_symlink_created(host_data_mount: testinfra.host.Host, folder: str) -> None:
    """/{folder} must be a symlink when /data is present."""
    path = f"/{folder}"
    f = host_data_mount.file(path)
    assert f.exists, f"{path} does not exist"
    assert f.is_symlink, f"{path} exists but is not a symlink"


@pytest.mark.parametrize("folder", DATA_SYMLINKED_FOLDERS)
def test_symlink_target(host_data_mount: testinfra.host.Host, folder: str) -> None:
    """/{folder} symlink must point to /data/{folder}."""
    path = f"/{folder}"
    f = host_data_mount.file(path)
    assert f.is_symlink, f"{path} is not a symlink"
    assert f.linked_to == f"/data/{folder}", (
        f"{path} points to {f.linked_to!r}, expected /data/{folder}"
    )


def test_viseron_process_running_data_mount(
    host_data_mount: testinfra.host.Host,
) -> None:
    """The viseron python process must be running in data-mount mode."""
    cmd = host_data_mount.run("pgrep -f 'python3 .*-m viseron'")
    assert cmd.rc == 0, (
        f"no viseron process found: rc={cmd.rc}\n"
        f"stdout=\n{cmd.stdout}\nstderr=\n{cmd.stderr}"
    )


def test_webserver_responds_data_mount(
    host_data_mount: testinfra.host.Host,
    webserver_url_data_mount: str,
) -> None:
    """The nginx-fronted webserver should respond in data-mount mode."""
    status = helpers.wait_for_http_in_container(
        host_data_mount, webserver_url_data_mount, timeout=30.0
    )
    assert status in (200, 301, 302, 401, 403), (
        f"unexpected status {status} from {webserver_url_data_mount}"
    )


def test_boot_logs_have_no_tracebacks_data_mount(boot_logs_data_mount: str) -> None:
    """Boot logs must not contain a Python traceback in data-mount mode."""
    matches = [
        match.group(0)
        for match in _FATAL_LOG_PATTERNS[0].finditer(boot_logs_data_mount)
    ]
    assert not matches, (
        f"found {len(matches)} traceback(s) in boot logs. First 2KB:\n"
        f"{boot_logs_data_mount[:2048]}"
    )


def test_boot_logs_have_no_errors_data_mount(boot_logs_data_mount: str) -> None:
    """Boot logs must not contain Viseron ERROR lines in data-mount mode."""
    matches = [
        match.group(0)
        for match in _FATAL_LOG_PATTERNS[1].finditer(boot_logs_data_mount)
    ]
    assert not matches, (
        f"found {len(matches)} ERROR log line(s) in boot logs. First 2KB:\n"
        f"{boot_logs_data_mount[:2048]}"
    )


def test_boot_logs_confirm_symlinking_ran(boot_logs_data_mount: str) -> None:
    """Boot logs must contain the 'Symlinking folders to /data' message.

    This confirms the init script took the /data-present branch rather than
    the normal (individual mounts) path.
    """
    assert "Symlinking folders to /data" in boot_logs_data_mount, (
        "Expected 'Symlinking folders to /data' in boot logs — "
        "the /data branch of 10-adduser may not have run.\n"
        f"First 2KB:\n{boot_logs_data_mount[:2048]}"
    )


@pytest.mark.parametrize("folder", DATA_SYMLINKED_FOLDERS)
def test_data_subdir_owned_by_abc(
    host_data_mount: testinfra.host.Host, folder: str
) -> None:
    """/data/{folder} must be owned by the abc user after chown in 10-adduser."""
    path = f"/data/{folder}"
    f = host_data_mount.file(path)
    assert f.exists, f"{path} does not exist"
    assert f.user == "abc", f"{path} is owned by {f.user!r}, expected 'abc'"
    assert f.group == "abc", f"{path} group is {f.group!r}, expected 'abc'"


def test_boot_logs_confirm_chown_skipped_when_disabled(
    boot_logs_data_mount_disable_chown: str,
) -> None:
    """Boot logs should confirm chown was skipped for volume paths."""
    assert "VISERON_DISABLE_CHOWN is enabled" in boot_logs_data_mount_disable_chown, (
        "Expected a log line confirming chown is disabled when VISERON_DISABLE_CHOWN is"
        " set. First 2KB:\n"
        f"{boot_logs_data_mount_disable_chown[:2048]}"
    )


@pytest.mark.parametrize("folder", DATA_SYMLINKED_FOLDERS)
def test_data_subdir_not_owned_by_abc_when_chown_disabled(
    host_data_mount_disable_chown: testinfra.host.Host,
    folder: str,
) -> None:
    """/data/{folder} should keep root ownership when chown is disabled."""
    path = f"/data/{folder}"
    f = host_data_mount_disable_chown.file(path)
    assert f.exists, f"{path} does not exist"
    assert f.user != "abc", f"{path} unexpectedly owned by {f.user!r}"
    assert f.group != "abc", f"{path} unexpectedly grouped to {f.group!r}"
