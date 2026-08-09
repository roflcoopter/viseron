"""Architecture-specific binary expectations for container smoke tests."""

from __future__ import annotations

GO2RTC_BINARY = "/usr/local/bin/go2rtc"
VAINFO_BINARY = "/usr/bin/vainfo"

COMMON_CRITICAL_BINARIES = (
    "/ffmpeg/bin/ffmpeg",
    "/ffmpeg/bin/ffprobe",
    "/ffmpeg/bin/zmqsend",
    "/ffmpeg/bin/qt-faststart",
    GO2RTC_BINARY,
    "/usr/sbin/nginx",
    "/usr/bin/MP4Box",
    "/usr/bin/clinfo",
)

ARCH_CRITICAL_BINARIES = {
    "amd64": (VAINFO_BINARY,),
    "amd64-cuda": (VAINFO_BINARY,),
    "aarch64": (),
    "rpi3": (),
}

# Shared-library names (as regex fragments) that are known to require specific
# hardware and therefore will legitimately be absent on a stock CI agent
ARCH_OPTIONAL_SO_PATTERNS: dict[str, tuple[str, ...]] = {
    "amd64-cuda": (
        r"libcuda\.so\.",  # CUDA driver,requires NVIDIA GPU + driver
        r"libcudart\.so\.",  # CUDA runtime (system copy)
        r"libtriton\.so",  # Triton, Ultralytics dependency
        r"libmlx5\.so\.",  # Mellanox ConnectX InfiniBand
        r"librdmacm\.so\.",  # RDMA connection manager
        r"libibverbs\.so\.",  # InfiniBand verbs
        r"libfabric\.so\.",  # OpenFabrics libfabric (HPC interconnect)
        r"libmpi\.so\.",  # MPI (e.g. OpenMPI)
        r"libpmix\.so\.",  # PMIx process management
        r"liboshmem\.so\.",  # OpenSHMEM
        r"libucs\.so\.",  # UCX common services
        r"libucp\.so\.",  # UCX protocols
    ),
}


def expected_critical_binaries(arch: str) -> tuple[str, ...]:
    """Return binaries that must exist in an image for ``arch``."""
    if arch not in ARCH_CRITICAL_BINARIES:
        raise ValueError(
            f"No critical binary expectations declared for architecture {arch!r}"
        )
    return (*COMMON_CRITICAL_BINARIES, *ARCH_CRITICAL_BINARIES[arch])


def binary_expected_for_arch(binary: str, arch: str) -> bool:
    """Return True if ``binary`` is required for ``arch``."""
    return binary in expected_critical_binaries(arch)


def binary_test_id(binary: str) -> str:
    """Return a readable pytest ID for a binary path."""
    return binary.removeprefix("/").replace("/", "-")
