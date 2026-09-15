"""Verify the Viseron application boots and serves traffic."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any

from . import _helpers as helpers

if TYPE_CHECKING:
    import testinfra

# Lines that we treat as fatal in the boot logs.
FATAL_LOG_PATTERNS = (
    re.compile(r"^Traceback \(most recent call last\):", re.MULTILINE),
    re.compile(r"\b(viseron(\.[\w\.]+)?)\b\s+ERROR\b", re.IGNORECASE | re.MULTILINE),
)


def test_viseron_process_running(host: testinfra.host.Host) -> None:
    """The viseron python process must be running."""
    cmd = host.run("pgrep -f 'python3 .*-m viseron'")
    assert cmd.rc == 0, (
        f"no viseron process found: rc={cmd.rc}\n"
        f"stdout=\n{cmd.stdout}\nstderr=\n{cmd.stderr}"
    )


def test_viseron_wrapper_passes_interpreter_args_through(
    host: testinfra.host.Host,
) -> None:
    """`viseron` must act as a plain interpreter when given arguments.

    The wrapper spoofs argv[0], so Python resolves sys.executable back to it.
    multiprocessing boots the forkserver and the resource tracker by re-execing
    sys.executable with "-c <bootstrap>". If the wrapper swallowed those, each
    re-exec would start a second Viseron.
    """
    cmd = host.run("viseron -c 'print(\"interpreter\")'")
    assert cmd.rc == 0, (
        f"viseron -c failed: rc={cmd.rc}\nstdout=\n{cmd.stdout}\nstderr=\n{cmd.stderr}"
    )
    assert cmd.stdout.strip() == "interpreter", (
        "viseron did not behave as an interpreter; it likely booted Viseron "
        f"instead. stdout=\n{cmd.stdout}"
    )


def test_sys_executable_is_usable_for_reexec(host: testinfra.host.Host) -> None:
    """Re-execing sys.executable with -c must not boot a second Viseron."""
    cmd = host.run(
        "viseron -c 'import subprocess,sys;"
        'print(subprocess.run([sys.executable,"-c","print(42)"],'
        "capture_output=True,text=True).stdout.strip())'"
    )
    assert cmd.rc == 0, f"re-exec check failed: rc={cmd.rc}\nstderr=\n{cmd.stderr}"
    assert cmd.stdout.strip() == "42", (
        f"re-exec of sys.executable did not behave as an interpreter: {cmd.stdout}"
    )


def test_webserver_responds(host: testinfra.host.Host, webserver_url: str) -> None:
    """The nginx-fronted webserver should answer HTTP requests."""
    status = helpers.wait_for_http_in_container(host, webserver_url, timeout=30.0)
    assert status in (200, 301, 302, 401, 403), (
        f"unexpected status {status} from {webserver_url}"
    )


def test_boot_logs_have_no_tracebacks(boot_logs: str) -> None:
    """Boot logs must not contain a Python traceback."""
    matches = [match.group(0) for match in FATAL_LOG_PATTERNS[0].finditer(boot_logs)]
    assert not matches, (
        f"found {len(matches)} traceback(s) in boot logs. First 2KB of logs:\n"
        f"{boot_logs[:2048]}"
    )


def test_reload_wrapper_triggers_reload_log_and_keeps_process_running(
    host: testinfra.host.Host, viseron_container: Any
) -> None:
    """`viseron --reload` should trigger a reload log entry without killing Viseron."""
    pre_logs = viseron_container.logs().decode("utf-8", errors="replace")
    pre_requested_count = pre_logs.count("Config reload requested")
    pre_completed_count = pre_logs.count("Config reload completed in")
    pre_no_changes_count = pre_logs.count("No configuration changes detected")

    reload_cmd = host.run("viseron --reload")
    assert reload_cmd.rc == 0, (
        f"viseron --reload failed: rc={reload_cmd.rc}\n"
        f"stdout=\n{reload_cmd.stdout}\n"
        f"stderr=\n{reload_cmd.stderr}"
    )

    deadline = time.monotonic() + 30.0
    reload_logged = False
    reload_outcome_logged = False
    latest_logs = pre_logs
    while time.monotonic() < deadline:
        latest_logs = viseron_container.logs().decode("utf-8", errors="replace")
        requested_count = latest_logs.count("Config reload requested")
        completed_count = latest_logs.count("Config reload completed in")
        no_changes_count = latest_logs.count("No configuration changes detected")

        if requested_count > pre_requested_count:
            reload_logged = True

        # A completed reload can either apply changes or detect no config changes.
        if (
            completed_count > pre_completed_count
            or no_changes_count > pre_no_changes_count
        ):
            reload_outcome_logged = True

        if reload_logged and reload_outcome_logged:
            break
        time.sleep(0.5)

    assert reload_logged, (
        "Did not observe 'Config reload requested' in Viseron logs "
        "after invoking viseron --reload"
    )
    assert reload_outcome_logged, (
        "Did not observe either 'Config reload completed in' or "
        "'No configuration changes detected' after invoking viseron --reload\n"
        f"Last 4KB of logs:\n{latest_logs[-4096:]}"
    )

    running_cmd = host.run("pgrep -f '^viseron'")
    assert running_cmd.rc == 0, (
        f"viseron process not running after reload: rc={running_cmd.rc}\n"
        f"stdout=\n{running_cmd.stdout}\n"
        f"stderr=\n{running_cmd.stderr}"
    )
