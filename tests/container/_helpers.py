"""Helpers shared across container smoke tests."""

from __future__ import annotations

import io
import os
import re
import tarfile
import time
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / "azure-pipelines" / ".env"


def parse_env_file(path: Path = ENV_FILE) -> dict[str, str]:
    """Parse the azure-pipelines/.env file into a flat dict.

    The file uses ``KEY=value`` and ``KEY="value"`` syntax.
    """
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith("#"):
            continue
        match = re.match(r'^([A-Z0-9_]+)\s*=\s*"?(.*?)"?\s*$', line_stripped)
        if not match:
            continue
        values[match.group(1)] = match.group(2)
    return values


EXPECTED = parse_env_file()


def wait_for_log(
    container: Any,
    pattern: str,
    timeout: float = 180.0,
    interval: float = 1.0,
) -> str:
    """Poll the container's logs until ``pattern`` matches, then return the logs.

    Raises ``TimeoutError`` on timeout.
    """
    compiled = re.compile(pattern)
    deadline = time.monotonic() + timeout
    last_logs = ""
    while time.monotonic() < deadline:
        last_logs = container.logs().decode("utf-8", errors="replace")
        if compiled.search(last_logs):
            return last_logs
        time.sleep(interval)
    raise TimeoutError(
        f"Pattern {pattern!r} not seen within {timeout}s. Last logs:\n{last_logs}"
    )


def wait_for_http(
    url: str,
    timeout: float = 60.0,
    interval: float = 1.0,
    accept_status: tuple[int, ...] = (200, 301, 302, 401, 403),
) -> requests.Response:
    """Poll ``url`` until it returns one of ``accept_status`` codes."""
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = requests.get(url, timeout=5, allow_redirects=True)
            if response.status_code in accept_status:
                return response
            last_exc = RuntimeError(f"Got status {response.status_code} from {url}")
        except requests.RequestException as exc:
            last_exc = exc
        time.sleep(interval)
    raise TimeoutError(f"Timed out waiting for {url}: {last_exc}")


# Probe script lives next to this file and is shipped into the container with
# ``install_http_probe`` (via the Docker SDK's ``put_archive``).  We can't
# rely on bind-mounting because in the dev-container environment the test
# process and the Docker daemon are on different filesystems.
HTTP_PROBE_SOURCE = Path(__file__).parent / "scripts" / "http_probe.py"
HTTP_PROBE_CONTAINER_PATH = "/tmp/viseron_http_probe.py"  # noqa: S108


def _make_tar(items: dict[str, bytes]) -> bytes:
    """Return an in-memory tar archive containing ``items``.

    ``items`` maps archive-relative paths (relative to the extraction root) to
    file contents.  Parent directory entries are emitted automatically so
    ``put_archive`` can create them even when they don't already exist in the
    container image.
    """
    buf = io.BytesIO()
    dirs_added: set[str] = set()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in items.items():
            # Emit a directory entry for every ancestor that hasn't been added.
            parts = name.split("/")
            for depth in range(1, len(parts)):
                dir_path = "/".join(parts[:depth])
                if dir_path not in dirs_added:
                    dir_info = tarfile.TarInfo(name=dir_path)
                    dir_info.type = tarfile.DIRTYPE
                    dir_info.mode = 0o755
                    tar.addfile(dir_info)
                    dirs_added.add(dir_path)
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))
    buf.seek(0)
    return buf.getvalue()


def put_abs(container: Any, container_path: str, data: bytes) -> None:
    """Stream ``data`` to an absolute path inside ``container``.

    Works regardless of whether intermediate directories exist in the
    container image: the tar archive includes directory entries for all
    parents, and Docker's extraction creates them on the fly.  This is
    necessary for paths like ``/config/config.yaml`` where ``/config`` is
    created by the S6 init scripts at *runtime*, not baked into the image.
    """
    rel = container_path.lstrip("/")  # e.g. "config/config.yaml"
    container.put_archive("/", _make_tar({rel: data}))


def create_directories(container: Any, *container_paths: str) -> None:
    """Create empty directories at the given absolute paths inside ``container``.

    Uses ``put_archive`` so it works regardless of filesystem visibility
    between the test process and the Docker daemon.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for path in container_paths:
            rel = path.lstrip("/")
            info = tarfile.TarInfo(name=rel)
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            tar.addfile(info)
    buf.seek(0)
    container.put_archive("/", buf.getvalue())


def put_file(container: Any, dest_dir: str, name: str, data: bytes) -> None:
    """Stream a single file into ``container`` at ``dest_dir/name``.

    ``dest_dir`` must already exist.  For paths whose parents may not yet
    exist in the image, use :func:`put_abs` instead.
    """
    container.put_archive(dest_dir, _make_tar({name: data}))


def put_directory(container: Any, src: Path, dest_dir: str) -> None:
    """Recursively stream all files under ``src`` into ``container:dest_dir``."""
    items: dict[str, bytes] = {}
    for path in src.rglob("*"):
        if path.is_file():
            items[str(path.relative_to(src))] = path.read_bytes()
    dest_prefix = dest_dir.lstrip("/")
    if items:
        abs_items = {
            f"{dest_prefix}/{rel_path}": data for rel_path, data in items.items()
        }
        container.put_archive("/", _make_tar(abs_items))


def install_http_probe(container: Any) -> str:
    """Stream ``http_probe.py`` into ``container`` and return its path.

    Uses `put_abs` so it works regardless of whether the test process
    and the Docker daemon share a filesystem and regardless of whether the
    target directory exists in the image.
    """
    put_abs(container, HTTP_PROBE_CONTAINER_PATH, HTTP_PROBE_SOURCE.read_bytes())
    return HTTP_PROBE_CONTAINER_PATH


def wait_for_http_in_container(
    host: Any,
    url: str,
    timeout: float = 60.0,
    interval: float = 1.0,
    accept_status: tuple[int, ...] = (200, 301, 302, 401, 403),
    probe_path: str = HTTP_PROBE_CONTAINER_PATH,
) -> int:
    """Poll ``url`` from *inside* the container until a known status code.

    Runs ``python3 <probe_path> <url>`` via testinfra's ``host.run`` so the
    probe executes in the container's own network namespace.

    Returns the HTTP status code that was accepted.  Raises ``TimeoutError``
    if no accepted status was observed before ``timeout`` elapses.
    """
    deadline = time.monotonic() + timeout
    last_output = ""
    while time.monotonic() < deadline:
        cmd = host.run(f"python3 {probe_path} {url}")
        last_output = (cmd.stdout + cmd.stderr).strip()
        if cmd.rc == 0:
            try:
                status = int(last_output.splitlines()[-1].strip())
            except (ValueError, IndexError):
                status = -1
            if status in accept_status:
                return status
        time.sleep(interval)
    raise TimeoutError(
        f"In-container probe of {url} timed out after {timeout}s. "
        f"Last output:\n{last_output}"
    )


def is_qemu(arch: str) -> bool:
    """Return True if the configured arch is being executed under qemu."""
    return os.environ.get("VISERON_SMOKE_QEMU") == "1" or arch == "rpi3"
