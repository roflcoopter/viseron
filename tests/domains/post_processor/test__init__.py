"""Tests for AbstractPostProcessor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from viseron.domains.camera.events import EventCameraEventData
from viseron.domains.post_processor import AbstractPostProcessor, PostProcessorFrame
from viseron.domains.post_processor.const import (
    CONFIG_CAMERAS,
    CONFIG_LABELS,
    CONFIG_MASK,
)

from tests.common import MockCamera, MockComponent

if TYPE_CHECKING:
    from collections.abc import Iterator

    import numpy as np
    import numpy.typing as npt

    from viseron.viseron_types import SupportedDomains

    from tests.conftest import MockViseron


CAMERA_IDENTIFIER = "test_camera"
COMPONENT = "test_post_processor"


class ConcretePostProcessor(AbstractPostProcessor):
    """Concrete implementation for testing AbstractPostProcessor."""

    def __post_init__(self, *args, **kwargs) -> None:
        """Post init hook."""

    def preprocess(self, frame: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
        """Return the frame unchanged."""
        return frame

    def process(self, post_processor_frame: PostProcessorFrame) -> None:
        """Do nothing."""


@pytest.fixture(autouse=True)
def patch_restartable_thread() -> Iterator[MagicMock]:
    """Patch RestartableThread so no live thread is spawned by the constructor."""
    with patch(
        "viseron.domains.post_processor.RestartableThread", autospec=True
    ) as mock_thread_cls:
        mock_thread_cls.return_value = MagicMock()
        yield mock_thread_cls


@pytest.fixture(name="post_processor")
def fixture_post_processor(vis: MockViseron) -> ConcretePostProcessor:
    """Return a post processor with a registered camera."""
    MockComponent(vis, COMPONENT)
    MockCamera(vis, identifier=CAMERA_IDENTIFIER)
    config: dict[str, Any] = {
        CONFIG_CAMERAS: {CAMERA_IDENTIFIER: {CONFIG_MASK: [], CONFIG_LABELS: []}}
    }
    post_processor = ConcretePostProcessor(vis, config, CAMERA_IDENTIFIER)
    # Discard the domain setup/registration events dispatched by MockCamera
    vis.dispatch_event.reset_mock()
    return post_processor


@pytest.mark.parametrize(
    "domain",
    [
        pytest.param("face_recognition", id="face_recognition"),
        pytest.param("image_classification", id="image_classification"),
        pytest.param("license_plate_recognition", id="license_plate_recognition"),
    ],
)
def test_insert_result_dispatches_db_operation_event(
    vis: MockViseron,
    post_processor: ConcretePostProcessor,
    domain: SupportedDomains,
) -> None:
    """Test that a stored result dispatches a camera event for the frontend."""
    data = {"label": "test", "confidence": 0.5}

    post_processor._insert_result(domain, "/snapshots/test.jpg", data)

    vis.dispatch_event.assert_called_once_with(
        f"{CAMERA_IDENTIFIER}/camera_event/{domain}/insert",
        EventCameraEventData(
            camera_identifier=CAMERA_IDENTIFIER,
            domain=domain,
            operation="insert",
            data=data,
        ),
    )
