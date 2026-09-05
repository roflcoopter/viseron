"""Smoke tests for ``rootfs/etc/cont-init.d/80-postgres``.

The default smoke container boots with no ``POSTGRES_DATABASE_URL`` and an empty
``/config``, so the init script takes its fresh-install path: ``initdb`` a new
cluster, create the ``viseron`` database and ``abc`` role, then patch
``postgresql.conf``.

The major-version upgrade branch is covered separately in
``test_postgres_upgrade.py`` because it needs a container seeded with an
old-version data directory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    import testinfra

SCRIPT = "/etc/cont-init.d/80-postgres"
PGDATA = "/config/postgresql"


def _psql(host: testinfra.host.Host, sql: str, database: str = "postgres") -> Any:
    """Run ``sql`` as the ``postgres`` role over the local socket."""
    return host.run(
        "s6-setuidgid postgres psql -tAc %s -d %s",
        sql,
        database,
    )


def _installed_pg_major(host: testinfra.host.Host) -> str:
    """Return the image's PostgreSQL major version from ``psql --version``."""
    cmd = host.run("psql --version")
    assert cmd.rc == 0, cmd.stderr
    return cmd.stdout.split()[2].split(".")[0]


def test_pgdata_env_points_at_config(host: testinfra.host.Host) -> None:
    """``40-set-env-vars`` should resolve ``PGDATA`` to ``/config/postgresql``."""
    env_file = host.file("/var/run/environment/PGDATA")
    assert env_file.exists
    assert env_file.content_string.strip() == PGDATA


def test_pgdata_initialised_and_owned_by_postgres(host: testinfra.host.Host) -> None:
    """The script ``initdb``s ``$PGDATA`` and ``chown``s it ``postgres:abc``."""
    data_dir = host.file(PGDATA)
    assert data_dir.exists, f"{PGDATA} was not created by 80-postgres"
    assert data_dir.is_directory
    assert data_dir.user == "postgres", (
        f"{PGDATA} owned by {data_dir.user!r}, expected 'postgres'"
    )
    assert data_dir.group == "abc", (
        f"{PGDATA} group is {data_dir.group!r}, expected 'abc'"
    )


def test_var_run_postgresql_created(host: testinfra.host.Host) -> None:
    """The script also creates ``/var/run/postgresql`` for the unix socket."""
    sock_dir = host.file("/var/run/postgresql")
    assert sock_dir.exists
    assert sock_dir.is_directory


def test_pg_version_file_matches_installed(host: testinfra.host.Host) -> None:
    """``$PGDATA/PG_VERSION`` must match the PostgreSQL shipped in the image."""
    version_file = host.file(f"{PGDATA}/PG_VERSION")
    assert version_file.exists
    assert version_file.content_string.strip() == _installed_pg_major(host)


def test_pg_isready(host: testinfra.host.Host) -> None:
    """``pg_isready`` should report the local server as accepting connections."""
    cmd = host.run("pg_isready -h /var/run/postgresql")
    assert cmd.rc == 0, (
        f"pg_isready failed: rc={cmd.rc}\nstdout=\n{cmd.stdout}\nstderr=\n{cmd.stderr}"
    )


def test_viseron_database_created(host: testinfra.host.Host) -> None:
    """``create_db`` must have created the ``viseron`` database."""
    cmd = _psql(host, "SELECT 1 FROM pg_database WHERE datname = 'viseron';")
    assert cmd.rc == 0, cmd.stderr
    assert cmd.stdout.strip() == "1", (
        f"viseron db not present:\nstdout=\n{cmd.stdout}\nstderr=\n{cmd.stderr}"
    )


def test_abc_role_created(host: testinfra.host.Host) -> None:
    """``create_db`` must have created the ``abc`` login role."""
    cmd = _psql(host, "SELECT 1 FROM pg_roles WHERE rolname = 'abc';")
    assert cmd.rc == 0, cmd.stderr
    assert cmd.stdout.strip() == "1"


def test_bootstrap_superuser_is_postgres(host: testinfra.host.Host) -> None:
    """The role with ``oid = 10`` must be ``postgres``."""
    cmd = _psql(host, "SELECT rolname FROM pg_roles WHERE oid = 10;")
    assert cmd.rc == 0, cmd.stderr
    assert cmd.stdout.strip() == "postgres"


def test_log_checkpoints_disabled(host: testinfra.host.Host) -> None:
    """The trailing ``sed`` must flip ``log_checkpoints`` off in the config."""
    conf = host.file(f"{PGDATA}/postgresql.conf").content_string
    assert "log_checkpoints = off" in conf, (
        "80-postgres did not set 'log_checkpoints = off' in postgresql.conf"
    )
    assert "#log_checkpoints = on" not in conf, (
        "the commented-out default 'log_checkpoints' line was left untouched"
    )


def test_viseron_database_is_usable_by_the_app(host: testinfra.host.Host) -> None:
    """The storage component must have run its migrations against the DB.

    An ``alembic_version`` table proves the database 80-postgres created is
    actually reachable and writable by Viseron, not just present.
    """
    cmd = _psql(
        host,
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version';",
        database="viseron",
    )
    assert cmd.rc == 0, cmd.stderr
    assert cmd.stdout.strip() == "1", "alembic_version table missing from viseron db"


def test_no_upgrade_leftover_dir_on_fresh_install(host: testinfra.host.Host) -> None:
    """A fresh install must not leave a ``$PGDATA-<old>`` directory behind."""
    cmd = host.run("ls -d /config/postgresql-*")
    assert cmd.rc != 0, f"unexpected upgrade leftover directory: {cmd.stdout.strip()}"


@pytest.mark.parametrize(
    "marker",
    [
        "Preparing PostgreSQL",
        "Database has not been initialized. Initializing...",
        "Database has not been created. Creating...",
    ],
)
def test_boot_logs_show_fresh_install(boot_logs: str, marker: str) -> None:
    """The boot logs must show 80-postgres taking the fresh-install path."""
    assert marker in boot_logs, (
        f"missing {marker!r} in boot logs. First 2KB:\n{boot_logs[:2048]}"
    )


def test_boot_logs_do_not_mention_external_db(boot_logs: str) -> None:
    """The external-database branch must not run for the default container."""
    assert "POSTGRES_DATABASE_URL is set" not in boot_logs


def test_external_db_url_short_circuits(host: testinfra.host.Host) -> None:
    """With ``POSTGRES_DATABASE_URL`` set the script must skip all local setup."""
    cmd = host.run(
        "POSTGRES_DATABASE_URL=%s bash %s",
        "postgresql://user:pass@example.invalid:5432/db",
        SCRIPT,
    )
    assert cmd.rc == 0, (
        f"script exited non-zero: rc={cmd.rc}\n"
        f"stdout=\n{cmd.stdout}\nstderr=\n{cmd.stderr}"
    )
    output = cmd.stdout + cmd.stderr
    assert "Skipping local PostgreSQL setup" in output
    assert "Updating PostgreSQL configuration" not in output, (
        "script continued into local setup despite POSTGRES_DATABASE_URL being set"
    )


def test_rerun_is_idempotent_when_already_initialised(
    host: testinfra.host.Host,
) -> None:
    """Re-running the script must take the "already initialised" branch."""
    cmd = host.run("bash %s", SCRIPT)
    assert cmd.rc == 0, (
        f"re-run exited non-zero: rc={cmd.rc}\n"
        f"stdout=\n{cmd.stdout}\nstderr=\n{cmd.stderr}"
    )
    output = cmd.stdout + cmd.stderr
    assert "Database has already been initialized." in output
    assert "Initializing..." not in output, (
        "script re-ran initdb on an existing cluster"
    )

    ready = host.run("pg_isready -h /var/run/postgresql")
    assert ready.rc == 0, f"server not accepting after script re-run: {ready.stdout}"
    still_there = _psql(host, "SELECT 1 FROM pg_database WHERE datname = 'viseron';")
    assert still_there.stdout.strip() == "1", "viseron db missing after script re-run"


def test_second_createdb_reports_database_exists(host: testinfra.host.Host) -> None:
    """The guard ``create_db`` relies on: the ``viseron`` DB genuinely exists."""
    cmd = host.run("s6-setuidgid postgres createdb -U postgres -O postgres viseron")
    assert cmd.rc != 0, "createdb unexpectedly succeeded; the viseron db was missing"
    assert "already exists" in (cmd.stdout + cmd.stderr).lower()
