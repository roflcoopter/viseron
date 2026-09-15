"""Tests for AbstractPostProcessor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, MagicMock, call, patch

import numpy as np
import pytest

from viseron.components.storage.const import LATEST_SNAPSHOT_FILENAME
from viseron.domains.camera.events import EventCameraEventData
from viseron.domains.camera.shared_frames import SharedFrame
from viseron.domains.post_processor import AbstractPostProcessor, PostProcessorFrame
from viseron.domains.post_processor.const import (
    CONFIG_CAMERAS,
    CONFIG_LABELS,
    CONFIG_MASK,
)
from viseron.viseron_types import SnapshotDomain

from tests.common import MockCamera, MockComponent

if TYPE_CHECKING:
    from collections.abc import Iterator

    import numpy.typing as npt

    from viseron.viseron_types import SupportedDomains

    from tests.conftest import MockViseron


CAMERA_IDENTIFIER = "test_camera"
COMPONENT = "test_post_processor"
SNAPSHOT_PATH = "/snapshots/face_recognition/test_camera/alice/snapshot.jpg"
LATEST_SNAPSHOT_PATH = (
    f"/snapshots/face_recognition/test_camera/{LATEST_SNAPSHOT_FILENAME}"
)


class ConcretePostProcessor(AbstractPostProcessor):
    """Concrete implementation for testing AbstractPostProcessor."""

    domain = "face_recognition"
    snapshot_domain = SnapshotDomain.FACE_RECOGNITION

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
    post_processor = ConcretePostProcessor(vis, COMPONENT, config, CAMERA_IDENTIFIER)
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


@pytest.mark.usefixtures("post_processor")
def test_latest_snapshot_entity_is_registered_for_unload(vis: MockViseron) -> None:
    """Test the entity is registered with the keys unload_domain_identifier uses."""
    vis.add_entity.assert_called_once_with(
        COMPONENT, ANY, "face_recognition", CAMERA_IDENTIFIER
    )


def test_save_snapshot_writes_unique_and_latest_file(
    post_processor: ConcretePostProcessor,
) -> None:
    """Test that a snapshot is written twice, the second time to the latest file."""
    camera = post_processor._camera
    camera.write_snapshot.side_effect = [SNAPSHOT_PATH, LATEST_SNAPSHOT_PATH]
    shared_frame = MagicMock(spec=SharedFrame)

    snapshot_path = post_processor._save_snapshot(shared_frame, subfolder="alice")

    frame = camera.build_snapshot_frame.return_value
    camera.build_snapshot_frame.assert_called_once_with(
        shared_frame,
        zoom_coordinates=None,
        detected_object=None,
        bbox=None,
        text=None,
    )
    assert camera.write_snapshot.call_args_list == [
        call(frame, SnapshotDomain.FACE_RECOGNITION, subfolder="alice"),
        call(
            frame,
            SnapshotDomain.FACE_RECOGNITION,
            filename=LATEST_SNAPSHOT_FILENAME,
        ),
    ]
    # The unique path is what gets stored in the database, not the latest path
    assert snapshot_path == SNAPSHOT_PATH


def test_save_snapshot_updates_entity_without_rereading_from_disk(
    post_processor: ConcretePostProcessor,
) -> None:
    """Test the entity is fed the in-memory frame that was written to disk."""
    frame = np.full((10, 10, 3), 7, dtype=np.uint8)
    camera = post_processor._camera
    camera.build_snapshot_frame.return_value = frame
    camera.write_snapshot.return_value = SNAPSHOT_PATH

    post_processor._save_snapshot(MagicMock(spec=SharedFrame))

    entity = post_processor._latest_snapshot_entity
    assert entity.image is not None
    np.testing.assert_array_equal(entity.image, frame)
    assert entity.extra_attributes["snapshot_path"] == SNAPSHOT_PATH
