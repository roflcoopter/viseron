"""Tests for the camera domain."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.const import DEFAULT_OUTPUT_FPS


def _calculate_output_fps(scan_fps: list[int]) -> int:
    """Run AbstractCamera.calculate_output_fps against a lightweight stub.

    Using a SimpleNamespace as ``self`` avoids the heavy camera ``__init__`` and
    the abstract ``output_fps`` property while still exercising the real logic.
    """
    stub = SimpleNamespace(output_fps=None)
    scanners = [SimpleNamespace(scan_fps=fps) for fps in scan_fps]
    AbstractCamera.calculate_output_fps(stub, scanners)  # type: ignore[arg-type]
    return stub.output_fps


class TestCalculateOutputFps:
    """Tests for AbstractCamera.calculate_output_fps."""

    def test_no_scanners_uses_default_output_fps(self):
        """No scanners -> output fps falls back to the default."""
        assert _calculate_output_fps([]) == DEFAULT_OUTPUT_FPS

    def test_single_scanner_uses_its_scan_fps(self):
        """Single scanner -> output fps equals its scan fps."""
        assert _calculate_output_fps([5]) == 5

    @pytest.mark.parametrize(
        ("scan_fps", "expected"),
        [
            ([1, 5, 3], 5),
            ([10, 2], 10),
            ([4, 4], 4),
        ],
    )
    def test_multiple_scanners_use_highest_scan_fps(
        self, scan_fps: list[int], expected: int
    ):
        """Multiple scanners -> output fps equals the highest scan fps."""
        assert _calculate_output_fps(scan_fps) == expected
