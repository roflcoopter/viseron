"""Tests for the camera domain."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.const import DEFAULT_OUTPUT_FPS
from viseron.domains.camera.shared_frames import SharedFrame
from viseron.viseron_types import SnapshotDomain

if TYPE_CHECKING:
    import numpy.typing as npt


RESOLUTION = (1920, 1080)
SNAPSHOTS_FOLDER = "/snapshots/face_recognition/test_camera"


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


def _build_snapshot_frame(
    frame: npt.NDArray[np.uint8], **kwargs
) -> npt.NDArray[np.uint8]:
    """Run AbstractCamera.build_snapshot_frame against a lightweight stub."""
    stub = SimpleNamespace(
        shared_frames=SimpleNamespace(
            get_decoded_frame_rgb=lambda _shared_frame: frame
        ),
        resolution=RESOLUTION,
    )
    return AbstractCamera.build_snapshot_frame(
        stub,  # type: ignore[arg-type]
        MagicMock(spec=SharedFrame),
        **kwargs,
    )


def _write_snapshot(frame: npt.NDArray[np.uint8], **kwargs) -> tuple[str, MagicMock]:
    """Run AbstractCamera.write_snapshot against a lightweight stub."""
    stub = SimpleNamespace(
        _get_folder=lambda _domain: SNAPSHOTS_FOLDER,
        _logger=MagicMock(),
    )
    with (
        patch("viseron.domains.camera.cv2.imwrite") as mock_imwrite,
        patch("viseron.domains.camera.create_directory"),
    ):
        path = AbstractCamera.write_snapshot(
            stub,  # type: ignore[arg-type]
            frame,
            SnapshotDomain.FACE_RECOGNITION,
            **kwargs,
        )
    return path, mock_imwrite


class TestBuildSnapshotFrame:
    """Tests for AbstractCamera.build_snapshot_frame."""

    def test_plain_frame_is_returned_unchanged(self) -> None:
        """No annotations -> the decoded frame is returned as-is."""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        assert _build_snapshot_frame(frame) is frame

    def test_detected_object_is_drawn(self) -> None:
        """A detected object is drawn onto the frame."""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        detected_object = MagicMock()

        with patch("viseron.domains.camera.draw_objects") as mock_draw_objects:
            result = _build_snapshot_frame(frame, detected_object=detected_object)

        mock_draw_objects.assert_called_once_with(frame, [detected_object])
        assert result is frame

    def test_bbox_is_annotated_with_absolute_coords(self) -> None:
        """A relative bbox is annotated using absolute coordinates."""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        with patch("viseron.domains.camera.annotate_frame") as mock_annotate_frame:
            _build_snapshot_frame(frame, bbox=(0.1, 0.1, 0.2, 0.2), text="ABC123 90%")

        mock_annotate_frame.assert_called_once_with(
            frame, (192, 108, 384, 216), "ABC123 90%"
        )

    def test_zoom_crops_the_frame(self) -> None:
        """Zoom coordinates crop the frame down to the zoomed region."""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        result = _build_snapshot_frame(frame, zoom_coordinates=(0.1, 0.1, 0.2, 0.2))

        # zoom_boundingbox enforces a 300px minimum crop size
        assert result.shape == (300, 300, 3)


class TestWriteSnapshot:
    """Tests for AbstractCamera.write_snapshot."""

    @pytest.mark.parametrize(
        ("kwargs", "expected_path"),
        [
            pytest.param(
                {"filename": "snapshot.jpg"},
                f"{SNAPSHOTS_FOLDER}/snapshot.jpg",
                id="fixed_filename",
            ),
            pytest.param(
                {"subfolder": "alice", "filename": "snapshot.jpg"},
                f"{SNAPSHOTS_FOLDER}/alice/snapshot.jpg",
                id="subfolder",
            ),
            pytest.param(
                {"filename": "latest_snapshot.jpg"},
                f"{SNAPSHOTS_FOLDER}/latest_snapshot.jpg",
                id="latest_snapshot_stays_in_domain_root",
            ),
        ],
    )
    def test_path_is_built_from_folder_subfolder_and_filename(
        self, kwargs: dict[str, str], expected_path: str
    ) -> None:
        """The returned path combines the domain folder, subfolder and filename."""
        frame = np.zeros((10, 10, 3), dtype=np.uint8)

        path, mock_imwrite = _write_snapshot(frame, **kwargs)

        assert path == expected_path
        mock_imwrite.assert_called_once_with(path, frame, [1, 100])

    def test_filename_is_generated_when_not_given(self) -> None:
        """Without a filename a unique one is generated in the domain folder."""
        frame = np.zeros((10, 10, 3), dtype=np.uint8)

        first, _ = _write_snapshot(frame)
        second, _ = _write_snapshot(frame)

        assert first.startswith(f"{SNAPSHOTS_FOLDER}/")
        assert first.endswith(".jpg")
        assert first != second
