"""Smoke test for the major-version upgrade branch of ``80-postgres``.

``upgrade_db`` only runs when ``$PGDATA/PG_VERSION`` differs from the PostgreSQL
version shipped in the image. To reproduce that, an extra ``cont-init.d`` script
seeds ``$PGDATA`` with a previous-major cluster owned by the ``abc`` bootstrap
superuser (matching Viseron's pre-2024 clusters) before ``80-postgres`` runs.

Seeding from ``cont-init.d`` rather than by mutating a booted container is
deliberate: the ``viseron`` service's ``finish`` script runs ``s6-svscanctl -t``
whenever Viseron exits, so stopping the service to free the data directory tears
down the whole container.

Needs outbound access to ``apt.postgresql.org``, the same requirement
``upgrade_db`` has in production.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import testinfra

from . import _helpers as helpers
from .conftest import _MINIMAL_CONFIG, READY_LOG_PATTERN, REQUIRED_STORAGE_DIRS

if TYPE_CHECKING:
    from collections.abc import Iterator

    import docker

pytestmark = pytest.mark.timeout(1200)

PGDATA = "/config/postgresql"

# Runs after 40-set-env-vars (which exports PG_VERSION/PGDATA) and before
# 80-postgres. The bootstrap superuser is ``abc`` in both seeds, matching the
# pre-cd4111fa layout; they differ only in whether a ``postgres`` login role is
# also created.
_SEED_SCRIPT_PATH = "/etc/cont-init.d/79-seed-old-cluster"
_SEED_DONE_MARKER = "[seed] old cluster ready"
_LEGACY_SEED_DONE_MARKER = "[seed] legacy cluster ready"

_SEED_HEAD = rb"""#!/usr/bin/with-contenv bash
set -ex

source /helpers/logger.sh
source /helpers/set_env.sh
. /etc/os-release

OLD=$((PG_VERSION - 1))
BIN=/usr/lib/postgresql/${OLD}/bin

log_info "[seed] building a PostgreSQL ${OLD} cluster at ${PGDATA}"

KEYRING=/usr/share/keyrings/postgresql-archive-keyring.gpg
KEY_URL=https://www.postgresql.org/media/keys/ACCC4CF8.asc
APT_URL=https://apt.postgresql.org/pub/repos/apt
curl -fsSL "$KEY_URL" | gpg --dearmor -o "$KEYRING"
echo "deb [signed-by=$KEYRING] $APT_URL ${UBUNTU_CODENAME}-pgdg main" \
  > /etc/apt/sources.list.d/pgdg.list
apt-get update
apt-get install -y --no-install-recommends postgresql-${OLD}

rm -rf "$PGDATA"
install -d -m 700 -o postgres -g abc "$PGDATA"
install -d -o postgres -g abc /var/run/postgresql

s6-setuidgid postgres ${BIN}/initdb -D "$PGDATA" -U abc
s6-setuidgid postgres ${BIN}/pg_ctl -D "$PGDATA" -l "$PGDATA/logfile" -w -t 60 start
s6-setuidgid postgres ${BIN}/createdb -U abc -O abc viseron
"""

_SEED_TAIL = rb"""s6-setuidgid postgres ${BIN}/pg_ctl -D "$PGDATA" -w -t 60 stop
chown -R abc:abc "$PGDATA"
"""

# Adds a ``postgres`` role alongside the ``abc`` bootstrap superuser, which is
# what the rename block sees on current clusters.
_POSTGRES_ROLE_SEED = rb"""s6-setuidgid postgres ${BIN}/psql -U abc -d viseron \
  -c 'CREATE ROLE "postgres" WITH SUPERUSER LOGIN;'
"""

# Leaves oid 10 as ``abc`` and creates no ``postgres`` role, matching the layout
# reported in #1498. A marker table checks that user data survives the upgrade.
_LEGACY_ROLE_SEED = rb"""s6-setuidgid postgres ${BIN}/psql -U abc -d viseron \
  -c 'CREATE TABLE upgrade_marker(id int);'
s6-setuidgid postgres ${BIN}/psql -U abc -d viseron \
  -c 'INSERT INTO upgrade_marker VALUES (42);'
"""

_SEED_SCRIPT = (
    _SEED_HEAD
    + _POSTGRES_ROLE_SEED
    + _SEED_TAIL
    + rb"""log_info "[seed] old cluster ready (PG_VERSION=$(cat "$PGDATA/PG_VERSION"))"
"""
)

# Reproduces the layout described in #1498: ``initdb`` ran as ``abc`` under the
# pre-cd4111fa init scripts, so no ``postgres`` role exists at all. ``upgrade_db``
# has to find a role that can connect before it can rename oid 10.
_LEGACY_SEED_SCRIPT = (
    _SEED_HEAD
    + _LEGACY_ROLE_SEED
    + _SEED_TAIL
    + rb"""log_info "[seed] legacy cluster ready \
(PG_VERSION=$(cat "$PGDATA/PG_VERSION"))"
"""
)


def _verify_seed_ran(logs: str, marker: str = _SEED_DONE_MARKER) -> None:
    """Raise if the injected ``cont-init.d`` seed script did not finish."""
    if marker not in logs:
        raise RuntimeError(
            f"{_SEED_SCRIPT_PATH} did not complete, so 80-postgres never saw an "
            f"old cluster. Last 8KB of logs:\n{logs[-8192:]}"
        )


def _boot_upgrade_container(
    *,
    docker_client: docker.DockerClient,
    image: str,
    docker_platform: str,
    boot_timeout: float,
    artifact_dir: Path,
    request: pytest.FixtureRequest,
    seed_script: bytes,
    seed_marker: str,
    label: str,
) -> Iterator[Any]:
    """Boot a container whose ``$PGDATA`` is an old-version cluster."""
    container_name = helpers.unique_container_name(f"viseron-smoke-pg-{label}")

    run_kwargs: dict[str, Any] = {
        "image": image,
        "name": container_name,
        "environment": {
            "PUID": str(os.getuid()),
            "PGID": str(os.getgid()),
            "TZ": "UTC",
        },
    }
    if Path("/dev/dri").exists():
        run_kwargs["devices"] = ["/dev/dri:/dev/dri"]
    if docker_platform:
        run_kwargs["platform"] = docker_platform

    print(  # noqa: T201
        f"\n[smoke] starting {label} pg-upgrade container {container_name} from {image}"
    )
    try:
        container = docker_client.containers.create(**run_kwargs)
    except Exception as exc:
        (artifact_dir / f"{container_name}-startup-error.txt").write_text(
            f"Container failed to create:\n{exc}\n", encoding="utf-8"
        )
        raise

    helpers.put_abs(container, "/config/config.yaml", _MINIMAL_CONFIG.read_bytes())
    helpers.create_directories(container, *REQUIRED_STORAGE_DIRS)
    helpers.put_abs(container, _SEED_SCRIPT_PATH, seed_script, mode=0o755)

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
            print(f"[smoke] could not capture pg-upgrade logs: {exc}")  # noqa: T201
        print(f"[smoke] artifacts saved to {artifact_dir}")  # noqa: T201

    try:
        # This boot additionally installs the old PostgreSQL, builds the seed
        # cluster and runs pg_upgrade before Viseron starts.
        logs = helpers.wait_for_log(
            container, READY_LOG_PATTERN, timeout=boot_timeout + 300
        )
        _verify_seed_ran(logs, seed_marker)
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
def pg_upgrade_container(
    docker_client: docker.DockerClient,
    image: str,
    docker_platform: str,
    boot_timeout: float,
    artifact_dir: Path,
    request: pytest.FixtureRequest,
) -> Iterator[Any]:
    """Boot a container whose ``$PGDATA`` is an old cluster with a postgres role."""
    yield from _boot_upgrade_container(
        docker_client=docker_client,
        image=image,
        docker_platform=docker_platform,
        boot_timeout=boot_timeout,
        artifact_dir=artifact_dir,
        request=request,
        seed_script=_SEED_SCRIPT,
        seed_marker=_SEED_DONE_MARKER,
        label="upgrade",
    )


@pytest.fixture(scope="session")
def pg_legacy_upgrade_container(
    docker_client: docker.DockerClient,
    image: str,
    docker_platform: str,
    boot_timeout: float,
    artifact_dir: Path,
    request: pytest.FixtureRequest,
) -> Iterator[Any]:
    """Boot a container whose ``$PGDATA`` has no ``postgres`` role at all.

    This is the layout reported in #1498: the pre-2024 init scripts ran
    ``initdb`` as ``abc``, so oid 10 is ``abc`` and no ``postgres`` role exists.
    """
    yield from _boot_upgrade_container(
        docker_client=docker_client,
        image=image,
        docker_platform=docker_platform,
        boot_timeout=boot_timeout,
        artifact_dir=artifact_dir,
        request=request,
        seed_script=_LEGACY_SEED_SCRIPT,
        seed_marker=_LEGACY_SEED_DONE_MARKER,
        label="legacy-upgrade",
    )


@pytest.fixture(scope="session")
def pg_upgrade_host(pg_upgrade_container: Any) -> testinfra.host.Host:
    """Return a testinfra host bound to the upgraded container."""
    return testinfra.get_host(f"docker://{pg_upgrade_container.name}")


@pytest.fixture(scope="session")
def pg_upgrade_boot_logs(pg_upgrade_container: Any) -> str:
    """Return the captured boot logs of the upgrade container."""
    return pg_upgrade_container.logs().decode("utf-8", errors="replace")


@pytest.fixture(scope="session")
def pg_versions(pg_upgrade_host: testinfra.host.Host) -> tuple[int, int]:
    """Return ``(old_major, new_major)`` PostgreSQL versions for the upgrade."""
    cmd = pg_upgrade_host.run("psql --version")
    assert cmd.rc == 0, cmd.stderr
    new = int(cmd.stdout.split()[2].split(".")[0])
    return new - 1, new


def test_upgrade_detected_version_mismatch(
    pg_upgrade_boot_logs: str, pg_versions: tuple[int, int]
) -> None:
    """The script must log the detected old/new version mismatch."""
    old, new = pg_versions
    expected = (
        f"Database version ({old}) is not the same as the installed "
        f"PostgreSQL version ({new})."
    )
    assert expected in pg_upgrade_boot_logs, (
        f"missing {expected!r} in logs. Last 4KB:\n{pg_upgrade_boot_logs[-4096:]}"
    )


@pytest.mark.parametrize(
    "marker",
    [
        "Upgrading database to new PostgreSQL version...",
        "Changing superuser role name to postgres...",
        "Running pg_upgrade...",
        "Upgrade complete.",
    ],
)
def test_upgrade_log_markers_present(pg_upgrade_boot_logs: str, marker: str) -> None:
    """Each stage of ``upgrade_db`` must be reflected in the logs."""
    assert marker in pg_upgrade_boot_logs, (
        f"missing {marker!r} in upgrade logs. Last 4KB:\n{pg_upgrade_boot_logs[-4096:]}"
    )


def test_upgrade_installed_old_postgres(
    pg_upgrade_boot_logs: str, pg_versions: tuple[int, int]
) -> None:
    """``upgrade_db`` must install the previous major version from apt."""
    old, _ = pg_versions
    assert f"Installing PostgreSQL {old}..." in pg_upgrade_boot_logs


@pytest.mark.parametrize(
    "failure_marker",
    ["pg_upgrade failed", "Failed to install PostgreSQL"],
)
def test_upgrade_reported_no_failure(
    pg_upgrade_boot_logs: str, failure_marker: str
) -> None:
    """The abort paths in ``upgrade_db`` must not have been taken."""
    assert failure_marker not in pg_upgrade_boot_logs


def test_pgdata_now_on_installed_version(
    pg_upgrade_host: testinfra.host.Host, pg_versions: tuple[int, int]
) -> None:
    """After the upgrade ``$PGDATA/PG_VERSION`` must be the image's version."""
    _, new = pg_versions
    version_file = pg_upgrade_host.file(f"{PGDATA}/PG_VERSION")
    assert version_file.exists
    assert version_file.content_string.strip() == str(new)


def test_old_data_dir_moved_aside_and_owned_by_abc(
    pg_upgrade_host: testinfra.host.Host, pg_versions: tuple[int, int]
) -> None:
    """The pre-upgrade cluster must be kept as ``$PGDATA-<old>`` owned by abc."""
    old, _ = pg_versions
    old_dir = pg_upgrade_host.file(f"{PGDATA}-{old}")
    assert old_dir.exists, f"{PGDATA}-{old} was not preserved"
    assert old_dir.is_directory
    assert old_dir.user == "abc", (
        f"{PGDATA}-{old} owned by {old_dir.user!r}, expected 'abc'"
    )
    assert old_dir.group == "abc"


def test_bootstrap_superuser_renamed_to_postgres(
    pg_upgrade_host: testinfra.host.Host,
) -> None:
    """The oid-10 rename dance must have restored ``postgres`` as superuser."""
    cmd = pg_upgrade_host.run(
        "s6-setuidgid postgres psql -tAc %s -d postgres",
        "SELECT rolname FROM pg_roles WHERE oid = 10;",
    )
    assert cmd.rc == 0, cmd.stderr
    assert cmd.stdout.strip() == "postgres"


@pytest.mark.parametrize(
    "sql",
    [
        pytest.param(
            "SELECT 1 FROM pg_database WHERE datname = 'viseron';", id="viseron-db"
        ),
        pytest.param("SELECT 1 FROM pg_roles WHERE rolname = 'abc';", id="abc-role"),
    ],
)
def test_upgrade_preserved_database_and_abc_role(
    pg_upgrade_host: testinfra.host.Host, sql: str
) -> None:
    """The ``viseron`` database and the ``abc`` role must survive the upgrade."""
    cmd = pg_upgrade_host.run("s6-setuidgid postgres psql -tAc %s -d postgres", sql)
    assert cmd.rc == 0, cmd.stderr
    assert cmd.stdout.strip() == "1"


def test_log_checkpoints_patched_on_upgraded_cluster(
    pg_upgrade_host: testinfra.host.Host,
) -> None:
    """The trailing ``sed`` must run against the freshly upgraded data dir."""
    conf = pg_upgrade_host.file(f"{PGDATA}/postgresql.conf").content_string
    assert "log_checkpoints = off" in conf
    assert "#log_checkpoints = on" not in conf


def test_pg_isready_after_upgrade(pg_upgrade_host: testinfra.host.Host) -> None:
    """The upgraded server must be accepting connections."""
    cmd = pg_upgrade_host.run("pg_isready -h /var/run/postgresql")
    assert cmd.rc == 0, (
        f"pg_isready failed after upgrade: rc={cmd.rc}\n"
        f"stdout=\n{cmd.stdout}\nstderr=\n{cmd.stderr}"
    )


@pytest.fixture(scope="session")
def pg_legacy_upgrade_host(
    pg_legacy_upgrade_container: Any,
) -> testinfra.host.Host:
    """Return a testinfra host bound to the legacy-layout container."""
    return testinfra.get_host(f"docker://{pg_legacy_upgrade_container.name}")


@pytest.fixture(scope="session")
def pg_legacy_upgrade_boot_logs(pg_legacy_upgrade_container: Any) -> str:
    """Return the captured boot logs of the legacy-layout container."""
    return pg_legacy_upgrade_container.logs().decode("utf-8", errors="replace")


def test_legacy_layout_booted_without_postgres_role(
    pg_legacy_upgrade_boot_logs: str,
) -> None:
    """The seed must have produced a cluster with no ``postgres`` role.

    Without this the test would silently fall back to the modern layout and stop
    covering the upgrade path described in #1498.
    """
    assert "[seed] legacy cluster ready" in pg_legacy_upgrade_boot_logs


def test_legacy_layout_upgrade_completed(
    pg_legacy_upgrade_boot_logs: str,
) -> None:
    """``upgrade_db`` must finish even though no ``postgres`` role existed."""
    for marker in (
        "Changing superuser role name to postgres...",
        "Renaming old superuser to postgres...",
        "Upgrade complete.",
    ):
        assert marker in pg_legacy_upgrade_boot_logs, (
            f"missing {marker!r}. Last 4KB:\n{pg_legacy_upgrade_boot_logs[-4096:]}"
        )
    assert "Aborting upgrade to preserve data." not in pg_legacy_upgrade_boot_logs
    assert "pg_upgrade failed" not in pg_legacy_upgrade_boot_logs


def test_legacy_layout_oid10_renamed_to_postgres(
    pg_legacy_upgrade_host: testinfra.host.Host,
) -> None:
    """The ``abc`` bootstrap superuser must end up named ``postgres``."""
    cmd = pg_legacy_upgrade_host.run(
        "s6-setuidgid postgres psql -tAc %s -d postgres",
        "SELECT rolname FROM pg_roles WHERE oid = 10;",
    )
    assert cmd.rc == 0, cmd.stderr
    assert cmd.stdout.strip() == "postgres"


def test_legacy_layout_cleaned_up_temporary_superuser(
    pg_legacy_upgrade_host: testinfra.host.Host,
) -> None:
    """The temporary superuser used for the rename must not be left behind."""
    cmd = pg_legacy_upgrade_host.run(
        "s6-setuidgid postgres psql -tAc %s -d postgres",
        "SELECT count(*) FROM pg_roles WHERE rolname = 'temp';",
    )
    assert cmd.rc == 0, cmd.stderr
    assert cmd.stdout.strip() == "0"


def test_legacy_layout_preserved_abc_role(
    pg_legacy_upgrade_host: testinfra.host.Host,
) -> None:
    """``createuser abc`` must run after the rename, as the new superuser."""
    cmd = pg_legacy_upgrade_host.run(
        "s6-setuidgid postgres psql -tAc %s -d postgres",
        "SELECT count(*) FROM pg_roles WHERE rolname = 'abc';",
    )
    assert cmd.rc == 0, cmd.stderr
    assert cmd.stdout.strip() == "1"
