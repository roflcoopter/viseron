"""Tests for AbstractImageClassification."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import numpy as np
import numpy.typing as npt
import pytest

from viseron.domains.camera.shared_frames import SharedFrame
from viseron.domains.image_classification import (
    AbstractImageClassification,
    ImageClassificationResult,
)
from viseron.domains.image_classification.const import CONFIG_EXPIRE_AFTER
from viseron.domains.post_processor import PostProcessorFrame
from viseron.domains.post_processor.const import (
    CONFIG_CAMERAS,
    CONFIG_LABELS,
    CONFIG_MASK,
)
from viseron.viseron_types import SnapshotDomain

from tests.common import MockCamera, MockComponent

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.conftest import MockViseron


CAMERA_IDENTIFIER = "test_camera"
COMPONENT = "test_image_classification"
SNAPSHOT_PATH = "/snapshots/image_classification/test.jpg"


class ConcreteImageClassification(AbstractImageClassification):
    """Concrete implementation for testing AbstractImageClassification.

    Tests control the classification results via set_result().
    """

    def __init__(
        self,
        vis: MockViseron,
        config: dict[str, Any],
        camera_identifier: str,
    ) -> None:
        super().__init__(vis, COMPONENT, config, camera_identifier)
        self._result: list[ImageClassificationResult] = []

    def preprocess(self, frame: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
        """Return the frame unchanged."""
        return frame

    def image_classification(
        self, _post_processor_frame: PostProcessorFrame
    ) -> list[ImageClassificationResult]:
        """Getter for the classification result."""
        return self._result

    def set_result(self, result: list[ImageClassificationResult]) -> None:
        """Configure what image_classification() returns on subsequent calls."""
        self._result = result


@pytest.fixture(autouse=True)
def patch_restartable_thread() -> Iterator[MagicMock]:
    """Patch RestartableThread so no live thread is spawned by the constructor."""
    with patch(
        "viseron.domains.post_processor.RestartableThread", autospec=True
    ) as mock_thread_cls:
        mock_thread_cls.return_value = MagicMock()
        yield mock_thread_cls


@pytest.fixture(name="mock_camera")
def fixture_mock_camera(vis: MockViseron) -> MockCamera:
    """Return a registered mock camera with mocked snapshots."""
    camera = MockCamera(vis, identifier=CAMERA_IDENTIFIER)
    camera.save_snapshot.return_value = SNAPSHOT_PATH
    return camera


@pytest.fixture(name="post_processor")
def fixture_post_processor(
    vis: MockViseron,
    mock_camera: MockCamera,  # noqa: ARG001  # pylint: disable=unused-argument
) -> ConcreteImageClassification:
    """Return a post processor with a registered camera, which must exist first."""
    MockComponent(vis, COMPONENT)
    config = {
        CONFIG_CAMERAS: {CAMERA_IDENTIFIER: {CONFIG_MASK: [], CONFIG_LABELS: []}},
        CONFIG_EXPIRE_AFTER: 0,
    }
    return ConcreteImageClassification(vis, config, CAMERA_IDENTIFIER)


@pytest.fixture(name="mock_shared_frame")
def fixture_mock_shared_frame() -> SharedFrame:
    """Return a mock SharedFrame."""
    shared_frame = MagicMock(spec=SharedFrame)
    shared_frame.camera_identifier = CAMERA_IDENTIFIER
    return shared_frame


def _post_processor_frame(shared_frame: SharedFrame | None) -> PostProcessorFrame:
    """Return a PostProcessorFrame for the given shared frame."""
    return PostProcessorFrame(
        camera_identifier=CAMERA_IDENTIFIER,
        shared_frame=shared_frame,  # type: ignore[arg-type]
        frame=np.zeros((10, 10, 3), dtype=np.uint8),
        detected_objects=[],
        filtered_objects=[],
    )


class TestAbstractImageClassification:
    """Test AbstractImageClassification."""

    def test_process_inserts_one_result_per_classification(
        self,
        post_processor: ConcreteImageClassification,
        mock_camera: MockCamera,
        mock_shared_frame: SharedFrame,
    ) -> None:
        """Test that each classification is stored as its own row."""
        post_processor.set_result(
            [
                ImageClassificationResult(CAMERA_IDENTIFIER, "package", 0.87),
                ImageClassificationResult(CAMERA_IDENTIFIER, "person", 0.412),
            ]
        )

        with patch.object(post_processor, "_insert_result") as mock_insert_result:
            post_processor.process(_post_processor_frame(mock_shared_frame))

        mock_camera.save_snapshot.assert_called_once_with(
            mock_shared_frame, SnapshotDomain.IMAGE_CLASSIFICATION
        )
        assert mock_insert_result.call_count == 2
        assert [call.args for call in mock_insert_result.call_args_list] == [
            (
                "image_classification",
                SNAPSHOT_PATH,
                {
                    "camera_identifier": CAMERA_IDENTIFIER,
                    "label": "package",
                    "confidence": 0.87,
                },
            ),
            (
                "image_classification",
                SNAPSHOT_PATH,
                {
                    "camera_identifier": CAMERA_IDENTIFIER,
                    "label": "person",
                    "confidence": 0.412,
                },
            ),
        ]

    @pytest.mark.parametrize(
        ("result", "shared_frame"),
        [
            pytest.param([], MagicMock(spec=SharedFrame), id="no_classifications"),
            pytest.param(
                [ImageClassificationResult(CAMERA_IDENTIFIER, "package", 0.87)],
                None,
                id="no_shared_frame",
            ),
        ],
    )
    def test_process_does_not_store_snapshot(
        self,
        post_processor: ConcreteImageClassification,
        mock_camera: MockCamera,
        result: list[ImageClassificationResult],
        shared_frame: SharedFrame | None,
    ) -> None:
        """Test that nothing is stored without a classification or a frame."""
        post_processor.set_result(result)

        with patch.object(post_processor, "_insert_result") as mock_insert_result:
            post_processor.process(_post_processor_frame(shared_frame))

        mock_camera.save_snapshot.assert_not_called()
        mock_insert_result.assert_not_called()
