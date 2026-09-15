"""Tests for PostProcessorSnapshotImage."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import numpy as np
import pytest

from viseron.domains.post_processor.image import PostProcessorSnapshotImage
from viseron.helpers import zoom_boundingbox
from viseron.viseron_types import SnapshotDomain

from tests.common import MockCamera

if TYPE_CHECKING:
    from tests.conftest import MockViseron


CAMERA_IDENTIFIER = "test_camera"
SNAPSHOT_PATH = "/snapshots/face_recognition/test_camera/alice/snapshot.jpg"


@pytest.fixture(name="entity")
def fixture_entity(vis: MockViseron) -> PostProcessorSnapshotImage:
    """Return an entity with vis assigned, as States.add_entity would."""
    camera = MockCamera(vis, identifier=CAMERA_IDENTIFIER)
    entity = PostProcessorSnapshotImage(vis, camera, SnapshotDomain.FACE_RECOGNITION)
    entity.vis = vis
    return entity


@pytest.mark.parametrize(
    ("snapshot_domain", "expected_object_id", "expected_name"),
    [
        pytest.param(
            SnapshotDomain.FACE_RECOGNITION,
            "test_camera_latest_face_recognition_snapshot",
            "test_camera Latest Face Recognition Snapshot",
            id="face_recognition",
        ),
        pytest.param(
            SnapshotDomain.IMAGE_CLASSIFICATION,
            "test_camera_latest_image_classification_snapshot",
            "test_camera Latest Image Classification Snapshot",
            id="image_classification",
        ),
        pytest.param(
            SnapshotDomain.LICENSE_PLATE_RECOGNITION,
            "test_camera_latest_license_plate_recognition_snapshot",
            "test_camera Latest License Plate Recognition Snapshot",
            id="license_plate_recognition",
        ),
    ],
)
def test_identity_is_scoped_to_camera_and_domain(
    vis: MockViseron,
    snapshot_domain: SnapshotDomain,
    expected_object_id: str,
    expected_name: str,
) -> None:
    """Test that each camera and post processor domain gets its own entity."""
    camera = MockCamera(vis, identifier=CAMERA_IDENTIFIER)
    camera.name = CAMERA_IDENTIFIER

    entity = PostProcessorSnapshotImage(vis, camera, snapshot_domain)

    assert entity.domain == "image"
    assert entity.object_id == expected_object_id
    assert entity.name == expected_name


def test_update_snapshot_publishes_state(
    entity: PostProcessorSnapshotImage,
) -> None:
    """Test that a new snapshot updates the image and publishes a state."""
    frame = np.full((10, 10, 3), 7, dtype=np.uint8)

    with patch.object(entity, "set_state") as mock_set_state:
        entity.update_snapshot(frame, SNAPSHOT_PATH)

    assert entity.image is not None
    np.testing.assert_array_equal(entity.image, frame)
    assert entity.extra_attributes["snapshot_path"] == SNAPSHOT_PATH
    assert entity.extra_attributes["updated_at"] is not None
    mock_set_state.assert_called_once()


def test_update_snapshot_after_unload_is_ignored(
    entity: PostProcessorSnapshotImage,
) -> None:
    """Test that a late update does not resurrect the entity in the registry.

    Entities are unloaded before the post processor thread is stopped, so an
    update can still arrive after unload.
    """
    entity.unload()

    with patch.object(entity, "set_state") as mock_set_state:
        entity.update_snapshot(np.zeros((10, 10, 3), dtype=np.uint8), SNAPSHOT_PATH)

    mock_set_state.assert_not_called()
    assert entity.image is None


def test_update_snapshot_does_not_retain_the_full_frame(
    entity: PostProcessorSnapshotImage,
) -> None:
    """Test that a zoomed snapshot does not keep the full resolution frame alive."""
    full_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    zoomed = zoom_boundingbox(full_frame, (100, 100, 200, 200))
    assert zoomed.base is not None, "zoom_boundingbox is expected to return a view"

    with patch.object(entity, "set_state"):
        entity.update_snapshot(zoomed, SNAPSHOT_PATH)

    assert entity.image is not None
    assert entity.image.base is None
    np.testing.assert_array_equal(entity.image, zoomed)
