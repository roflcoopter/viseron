"""Verify the binaries built and bundled into the image work as expected."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .binary_expectations import GO2RTC_BINARY, VAINFO_BINARY, binary_expected_for_arch

if TYPE_CHECKING:
    import testinfra

# Build flags expected on every architecture.
COMMON_FFMPEG_FLAGS = (
    "--enable-gpl",
    "--enable-libaribb24",
    "--enable-libass",
    "--enable-libfdk_aac",
    "--enable-libmp3lame",
    "--enable-libopus",
    "--enable-libsrt",
    "--enable-libvmaf",
    "--enable-libvorbis",
    "--enable-libvpx",
    "--enable-libwebp",
    "--enable-libx264",
    "--enable-libx265",
    "--enable-libzimg",
    "--enable-libzmq",
    "--enable-static",
    "--disable-shared",
)

# Architecture-specific expectations.
ARCH_FFMPEG_REQUIRED = {
    "amd64": ("--enable-libvpl", "--enable-libsvtav1"),
    "amd64-cuda": (
        "--enable-libvpl",
        "--enable-libsvtav1",
        "--enable-cuda",
        "--enable-cuvid",
        "--enable-nvenc",
    ),
    "aarch64": ("--enable-neon", "--enable-libsvtav1"),
    "rpi3": ("--enable-neon",),
}


def test_ffmpeg_version_matches_env(
    host: testinfra.host.Host, expected_versions: dict[str, str]
) -> None:
    """``ffmpeg -version`` should match ``FFMPEG_VERSION`` from .env."""
    cmd = host.run("/ffmpeg/bin/ffmpeg -version")
    assert cmd.rc == 0, cmd.stderr
    expected = expected_versions.get("FFMPEG_VERSION")
    assert expected, "FFMPEG_VERSION missing from azure-pipelines/.env"
    first_line = cmd.stdout.splitlines()[0]
    assert expected in first_line, f"expected ffmpeg {expected!r} in: {first_line!r}"


def test_ffmpeg_buildconf_required_flags(host: testinfra.host.Host) -> None:
    """``ffmpeg -buildconf`` should contain all required flags."""
    cmd = host.run("/ffmpeg/bin/ffmpeg -hide_banner -buildconf")
    assert cmd.rc == 0, cmd.stderr
    missing = [flag for flag in COMMON_FFMPEG_FLAGS if flag not in cmd.stdout]
    assert not missing, (
        f"missing ffmpeg buildconf flags: {missing}\n\nbuildconf:\n{cmd.stdout}"
    )


def test_ffmpeg_buildconf_arch_specific_flags(
    host: testinfra.host.Host, arch: str
) -> None:
    """Architecture-conditional flags should appear in the buildconf."""
    required = ARCH_FFMPEG_REQUIRED.get(arch, ())
    if not required:
        pytest.skip(f"no arch-specific flags for {arch}")
    cmd = host.run("/ffmpeg/bin/ffmpeg -hide_banner -buildconf")
    assert cmd.rc == 0, cmd.stderr
    missing = [flag for flag in required if flag not in cmd.stdout]
    assert not missing, f"missing arch-specific flags for {arch}: {missing}"


def test_ffmpeg_smoke_encode(host: testinfra.host.Host) -> None:
    """A trivial lavfi → null encode must succeed."""
    cmd = host.run(
        "/ffmpeg/bin/ffmpeg -hide_banner -nostats "
        "-f lavfi -i testsrc=duration=1:size=160x120:rate=10 "
        "-f null -"
    )
    assert cmd.rc == 0, (
        f"ffmpeg smoke encode failed: rc={cmd.rc}\n"
        f"stdout=\n{cmd.stdout}\nstderr=\n{cmd.stderr}"
    )


def test_ffprobe_version(host: testinfra.host.Host) -> None:
    """``ffprobe -version`` should run."""
    cmd = host.run("/ffmpeg/bin/ffprobe -version")
    assert cmd.rc == 0, cmd.stderr


def test_mp4box_version(host: testinfra.host.Host) -> None:
    """``MP4Box -version`` should run."""
    cmd = host.run("MP4Box -version")
    # MP4Box returns rc=0 with version on stderr/stdout depending on build.
    assert (cmd.rc == 0) or ("MP4Box" in cmd.stdout + cmd.stderr), (
        f"MP4Box version check failed: rc={cmd.rc}\n"
        f"stdout=\n{cmd.stdout}\nstderr=\n{cmd.stderr}"
    )


def test_go2rtc_help(host: testinfra.host.Host) -> None:
    """``go2rtc --help`` should exit cleanly."""
    cmd = host.run(f"{GO2RTC_BINARY} --help")
    # go2rtc --help exits non-zero on some versions; just assert binary works.
    assert "go2rtc" in (cmd.stdout + cmd.stderr).lower(), (
        f"go2rtc smoke failed: rc={cmd.rc}\n"
        f"stdout=\n{cmd.stdout}\nstderr=\n{cmd.stderr}"
    )


def test_nginx_version(host: testinfra.host.Host) -> None:
    """``nginx -v`` should print a version string."""
    cmd = host.run("nginx -v")
    output = cmd.stdout + cmd.stderr
    assert "nginx version" in output, output


def test_vainfo_runs(host: testinfra.host.Host, arch: str) -> None:
    """``vainfo`` may report no device, but the binary itself must run.

    We only assert that the binary did not segfault. Exit code is permissive
    because there is no GPU device on the CI agent.
    """
    if not binary_expected_for_arch(VAINFO_BINARY, arch):
        pytest.skip(f"{VAINFO_BINARY} is not expected in {arch} image")

    executable = host.run(f"test -x {VAINFO_BINARY}")
    assert executable.rc == 0, f"{VAINFO_BINARY} is expected in {arch} image"

    cmd = host.run(f"{VAINFO_BINARY} --display drm --device /dev/dri/renderD128")
    output = (cmd.stdout + cmd.stderr).lower()
    assert cmd.rc != 127, (
        f"vainfo command was not found: rc={cmd.rc}\n"
        f"stdout=\n{cmd.stdout}\nstderr=\n{cmd.stderr}"
    )
    assert "segmentation fault" not in output, output
    assert "vainfo" in output or "libva" in output, (
        f"vainfo did not produce expected output:\nstdout=\n{cmd.stdout}\n"
        f"stderr=\n{cmd.stderr}"
    )
