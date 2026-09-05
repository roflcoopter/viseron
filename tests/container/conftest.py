"""Shared fixtures for container smoke tests.

Boot the Viseron image once per test session, expose a ``testinfra`` host that
runs commands inside the container, and tear the container down even if a
test fails.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import docker
import pytest
import testinfra

from . import _helpers as helpers

if TYPE_CHECKING:
    from collections.abc import Iterator


# Container-side port nginx listens on.
NGINX_PORT = 8888

# Pattern logged by viseron once it has finished booting all components.
READY_LOG_PATTERN = r"Viseron initialized in [\d.]+ seconds"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register CLI options used by the container smoke tests."""
    parser.addoption(
        "--image",
        action="store",
        default=os.environ.get("VISERON_SMOKE_IMAGE", ""),
        help="Full image reference under test, e.g. roflcoopter/amd64-viseron:dev",
    )
    parser.addoption(
        "--arch",
        action="store",
        default=os.environ.get("VISERON_SMOKE_ARCH", "amd64"),
        choices=["amd64", "amd64-cuda", "aarch64", "rpi3"],
        help="Architecture being tested",
    )
    parser.addoption(
        "--docker-platform",
        action="store",
        default=os.environ.get("VISERON_SMOKE_PLATFORM", ""),
        help="Optional --platform value passed to docker run (e.g. linux/arm/v7)",
    )
    parser.addoption(
        "--boot-timeout",
        action="store",
        type=float,
        default=float(os.environ.get("VISERON_SMOKE_BOOT_TIMEOUT", "300")),
        help="Seconds to wait for Viseron to log readiness",
    )
    parser.addoption(
        "--keep-container",
        action="store_true",
        default=False,
        help="Do not stop/remove the container on teardown (debug aid)",
    )


# Every test is tagged with the container fixture it ultimately depends on, so
# that `-n <N> --dist loadgroup` keeps all tests sharing a container on one
# worker. Without this xdist spreads them round-robin and each worker boots its
# own copy of every container, which is slower than running serially.
# Booting a container dominates the runtime here, so the useful worker count is
# the number of groups below, not the number of CPUs.
CONTAINER_FIXTURE_GROUPS = (
    ("pg_upgrade_container", "pg_upgrade"),
    ("viseron_container_data_mount", "data_mount"),
    ("viseron_container_data_mount_disable_chown", "data_mount"),
    ("image_container", "image"),
    ("viseron_container", "main"),
)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Tag each test with the xdist group of the container it needs."""
    if not config.pluginmanager.hasplugin("xdist"):
        return
    for item in items:
        fixtures = set(getattr(item, "fixturenames", ()))
        for fixture_name, group in CONTAINER_FIXTURE_GROUPS:
            if fixture_name in fixtures:
                item.add_marker(pytest.mark.xdist_group(group))
                break


@pytest.fixture(scope="session")
def image(request: pytest.FixtureRequest) -> str:
    """Return the image reference under test."""
    value = request.config.getoption("--image")
    if not value:
        pytest.fail(
            "--image is required (e.g. roflcoopter/amd64-viseron:dev) or set "
            "VISERON_SMOKE_IMAGE env var"
        )
    return value


@pytest.fixture(scope="session")
def arch(request: pytest.FixtureRequest) -> str:
    """Return the architecture under test."""
    return request.config.getoption("--arch")


@pytest.fixture(scope="session")
def docker_platform(request: pytest.FixtureRequest, arch: str) -> str:
    """Return the docker --platform value to use."""
    explicit = request.config.getoption("--docker-platform")
    if explicit:
        return explicit
    return {
        "amd64": "linux/amd64",
        "amd64-cuda": "linux/amd64",
        "aarch64": "linux/arm64",
        "rpi3": "linux/arm/v7",
    }.get(arch, "")


@pytest.fixture(scope="session")
def boot_timeout(request: pytest.FixtureRequest, arch: str) -> float:
    """Return the boot timeout, with a longer default for QEMU runs."""
    explicit = request.config.getoption("--boot-timeout")
    # Bump default for QEMU so emulated startup is not flaky.
    if helpers.is_qemu(arch) and explicit <= 30:
        return 60.0
    return explicit


@pytest.fixture(scope="session")
def docker_client() -> docker.DockerClient:
    """Return a docker client wired to the local daemon."""
    return docker.from_env()


# Source config used when seeding the container's /config directory.
_MINIMAL_CONFIG = Path(__file__).parent / "configs" / "minimal.yaml"

# Container paths that Viseron expects to exist and be writable at startup.
REQUIRED_STORAGE_DIRS = (
    "/recordings",
    "/segments",
    "/snapshots",
    "/thumbnails",
    "/event_clips",
)


@pytest.fixture(scope="session")
def artifact_dir(request: pytest.FixtureRequest) -> Path:
    """Return (and create) the directory where smoke-test artifacts are written.

    Resolving this in its own fixture guarantees the directory exists even when
    ``viseron_container`` fails before its own body runs (e.g. a fixture
    dependency error), which would otherwise leave the directory empty.
    """
    path = Path(
        os.environ.get(
            "VISERON_SMOKE_ARTIFACT_DIR",
            str(Path(request.config.rootpath) / "smoke-artifacts"),
        )
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(scope="session")
def image_container(
    docker_client: docker.DockerClient,
    image: str,
    docker_platform: str,
    artifact_dir: Path,
    request: pytest.FixtureRequest,
) -> Iterator[Any]:
    """Start the image with s6 bypassed, for tests that only inspect its contents."""
    container_name = helpers.unique_container_name("viseron-smoke-image")

    run_kwargs: dict[str, Any] = {
        "image": image,
        "name": container_name,
        "entrypoint": ["sleep", "infinity"],
    }
    if Path("/dev/dri").exists():
        run_kwargs["devices"] = ["/dev/dri:/dev/dri"]
    if docker_platform:
        run_kwargs["platform"] = docker_platform

    print(  # noqa: T201
        f"\n[smoke] starting image-inspection container {container_name} from {image}"
    )
    container = docker_client.containers.create(**run_kwargs)
    try:
        container.start()
    except Exception as exc:
        (artifact_dir / f"{container_name}-startup-error.txt").write_text(
            f"Container failed to start:\n{exc}\n", encoding="utf-8"
        )
        container.remove(force=True)
        raise

    yield container

    if request.config.getoption("--keep-container"):
        print(  # noqa: T201
            f"[smoke] --keep-container set; leaving {container_name} running"
        )
        return

    try:
        container.stop(timeout=5)
    finally:
        container.remove(force=True)


@pytest.fixture(scope="session")
def image_host(image_container: Any) -> testinfra.host.Host:
    """Return a testinfra host bound to the non-booted image container."""
    return testinfra.get_host(f"docker://{image_container.name}")


@pytest.fixture(scope="session")
def viseron_container(
    docker_client: docker.DockerClient,
    image: str,
    docker_platform: str,
    boot_timeout: float,
    artifact_dir: Path,
    request: pytest.FixtureRequest,
) -> Iterator[Any]:
    """Start the Viseron container and yield it once it has booted.

    Configuration and helper scripts are pushed into the container via
    ``put_archive`` rather than bind-mounts. This works in every supported
    environment including VS Code dev containers, where the test process and
    the Docker daemon sit on different filesystems so volume paths in the test
    process are not visible to the daemon.
    """
    container_name = helpers.unique_container_name("viseron-smoke")

    run_kwargs: dict[str, Any] = {
        "image": image,
        "name": container_name,
        "environment": {
            "PUID": str(os.getuid()),
            "PGID": str(os.getgid()),
            "TZ": "UTC",
        },
        # Let Docker pick the host port
        "ports": {f"{NGINX_PORT}/tcp": None},
    }
    if Path("/dev/dri").exists():
        run_kwargs["devices"] = ["/dev/dri:/dev/dri"]
    if docker_platform:
        run_kwargs["platform"] = docker_platform

    print(  # noqa: T201
        f"\n[smoke] starting container {container_name} from {image} "
        f"(platform={docker_platform or 'default'})"
    )
    try:
        container = docker_client.containers.create(**run_kwargs)
    except Exception as exc:
        (artifact_dir / f"{container_name}-startup-error.txt").write_text(
            f"Container failed to create:\n{exc}\n", encoding="utf-8"
        )
        raise

    # Seed /config and required storage directories via the Docker socket
    # before starting so Viseron reads the correct config from boot.
    # Using put_abs/create_directories (not bind-mounts) so this works
    # regardless of filesystem visibility, and regardless of whether the paths
    # exist in the image at create-time (they may be created by S6 init scripts).
    helpers.put_abs(container, "/config/config.yaml", _MINIMAL_CONFIG.read_bytes())
    helpers.create_directories(container, *REQUIRED_STORAGE_DIRS)
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
        """Dump container logs and inspect data on failure."""
        try:
            (artifact_dir / f"{container_name}.log").write_bytes(
                container.logs(stdout=True, stderr=True)
            )
        except Exception as exc:  # pylint: disable=broad-except # noqa: BLE001
            print(f"[smoke] could not capture logs: {exc}")  # noqa: T201
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
def host(viseron_container: Any) -> testinfra.host.Host:
    """Return a testinfra host bound to the running container."""
    return testinfra.get_host(f"docker://{viseron_container.name}")


@pytest.fixture(scope="session")
def webserver_url(viseron_container: Any) -> str:
    """Return the URL used to probe the nginx-fronted webserver.

    The URL is intentionally the *internal* container address (loopback +
    container-side nginx port).  Tests probe this URL from inside the
    container via ``host.run`` so the test runner does not need network
    reachability to the container's published port.
    """
    _ = viseron_container
    return f"http://127.0.0.1:{NGINX_PORT}"


@pytest.fixture(scope="session")
def expected_versions() -> dict[str, str]:
    """Return version constants sourced from azure-pipelines/.env."""
    return helpers.EXPECTED


@pytest.fixture(scope="session")
def boot_logs(viseron_container: Any) -> str:
    """Return the captured logs from the boot."""
    return viseron_container.logs().decode("utf-8", errors="replace")
