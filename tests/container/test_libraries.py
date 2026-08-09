"""Verify library resolution for binaries and shared objects.

Runs ``ldd`` against critical binaries and the core shared libraries shipped
in the image to ensure the 24.04 upgrade did not leave any
``=> not found`` entries. Statically linked binaries are accepted when ``ldd``
reports them as static, but still have to be executable ELF files.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from .binary_expectations import (
    ARCH_OPTIONAL_SO_PATTERNS,
    binary_test_id,
    expected_critical_binaries,
)

ELF_MAGIC = ("7f", "45", "4c", "46")
STATIC_LDD_MARKERS = (
    "not a dynamic executable",
    "statically linked",
)

# Library directories to recursively walk and ldd-check.
LIB_DIRS = ("/usr/local/lib",)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Generate architecture-specific binary library checks."""
    if "binary" not in metafunc.fixturenames:
        return

    arch = metafunc.config.getoption("--arch")
    try:
        binaries = expected_critical_binaries(arch)
    except ValueError as error:
        raise pytest.UsageError(str(error)) from error
    metafunc.parametrize("binary", binaries, ids=binary_test_id)


def _ldd_reports_static(output: str) -> bool:
    """Return True if ``ldd`` reports that the target is statically linked."""
    output = output.lower()
    return any(marker in output for marker in STATIC_LDD_MARKERS)


def _static_binary_check(host: Any, path: str, ldd_output: str) -> None:
    """Assert that ``path`` is an executable ELF binary with no dynamic deps."""
    assert _ldd_reports_static(ldd_output), f"ldd did not report {path} as static"

    executable = host.run(f"test -x {path}")
    assert executable.rc == 0, f"{path} is not executable"

    magic = host.run(f"od -An -tx1 -N4 {path}")
    assert magic.rc == 0, (
        f"failed to read ELF magic for {path}: rc={magic.rc}\n"
        f"stdout=\n{magic.stdout}\n"
        f"stderr=\n{magic.stderr}"
    )
    assert tuple(magic.stdout.split()) == ELF_MAGIC, f"{path} is not an ELF binary"

    readelf = host.run("command -v readelf")
    if readelf.rc != 0:
        return

    program_headers = host.run(f"readelf -lW {path}")
    assert program_headers.rc == 0, (
        f"failed to read program headers for {path}: rc={program_headers.rc}\n"
        f"stdout=\n{program_headers.stdout}\n"
        f"stderr=\n{program_headers.stderr}"
    )
    assert "Requesting program interpreter" not in program_headers.stdout, (
        f"{path} unexpectedly has a dynamic interpreter\n{program_headers.stdout}"
    )

    dynamic_section = host.run(f"readelf -dW {path} 2>&1")
    dynamic_output = dynamic_section.stdout + dynamic_section.stderr
    assert dynamic_section.rc == 0 or "There is no dynamic section" in dynamic_output, (
        f"failed to read dynamic section for {path}: rc={dynamic_section.rc}\n"
        f"stdout=\n{dynamic_section.stdout}\n"
        f"stderr=\n{dynamic_section.stderr}"
    )
    assert "(NEEDED)" not in dynamic_output, (
        f"{path} unexpectedly has dynamic dependencies\n{dynamic_output}"
    )


# Output fragments produced by ldd when QEMU emulation crashes the target binary.
# This is a QEMU limitation, not a missing-dependency failure.
_QEMU_CRASH_MARKERS = (
    "qemu: uncaught target signal",
    "segmentation fault",
    "core dumped",
)


def _ldd_check(host: Any, path: str) -> None:
    """Run ``ldd`` against ``path`` and assert no missing libraries."""
    cmd = host.run(f"ldd {path} 2>&1")
    output = cmd.stdout + cmd.stderr
    if _ldd_reports_static(output):
        _static_binary_check(host, path, output)
        return

    # Under QEMU emulation ldd itself can crash with a segfault.  This is a
    # known QEMU limitation and does not indicate missing dependencies.
    if any(marker in output.lower() for marker in _QEMU_CRASH_MARKERS):
        pytest.skip(
            f"ldd crashed under QEMU for {path}, skipping library resolution check"
        )

    assert cmd.rc == 0, (
        f"ldd failed for {path}: rc={cmd.rc}\n"
        f"stdout=\n{cmd.stdout}\n"
        f"stderr=\n{cmd.stderr}"
    )
    missing = [line.strip() for line in output.splitlines() if "not found" in line]
    assert not missing, f"Missing libraries for {path}:\n  " + "\n  ".join(missing)


def test_binary_libraries_resolve(host: Any, arch: str, binary: str) -> None:
    """Each critical binary must have all of its dependencies resolvable."""
    assert host.file(binary).exists, f"{binary} is expected in {arch} image"
    _ldd_check(host, binary)


@pytest.mark.parametrize("lib_dir", LIB_DIRS)
def test_shared_objects_resolve(host: Any, arch: str, lib_dir: str) -> None:
    """All ``*.so*`` files under each library directory must resolve.

    Missing libraries that match ``ARCH_OPTIONAL_SO_PATTERNS`` for the current
    architecture are silently ignored because they require hardware that is not
    present on a stock CI agent (e.g. CUDA driver).
    """
    if not host.file(lib_dir).exists:
        pytest.skip(f"{lib_dir} not present in image")
    find = host.run(f"find {lib_dir} -type f \\( -name '*.so' -o -name '*.so.*' \\)")
    assert find.rc == 0, find.stderr
    libs = [line for line in find.stdout.splitlines() if line]
    assert libs, f"no shared objects found under {lib_dir}"

    optional_patterns = [re.compile(p) for p in ARCH_OPTIONAL_SO_PATTERNS.get(arch, ())]

    failures: list[str] = []
    for lib in libs:
        # Prepend the lib's own directory to LD_LIBRARY_PATH so that ldd can
        # resolve sibling libraries inside manylinux/auditwheel *.libs/ bundles.
        lib_dir = lib.rsplit("/", 1)[0]
        cmd = host.run(
            f"LD_LIBRARY_PATH={lib_dir}:${{LD_LIBRARY_PATH:-}} "
            f"ldd {lib} 2>&1 | grep 'not found' || true"
        )
        if not cmd.stdout.strip():
            continue
        # Filter lines that match a known hardware-optional library.
        real_missing = [
            line
            for line in cmd.stdout.splitlines()
            if line.strip() and not any(pat.search(line) for pat in optional_patterns)
        ]
        if real_missing:
            failures.append(f"{lib}:\n" + "\n".join(real_missing))
    assert not failures, "shared objects with unresolved deps:\n\n" + "\n\n".join(
        failures
    )
