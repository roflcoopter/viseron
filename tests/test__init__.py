"""Test Viseron."""

from unittest.mock import patch

from viseron import setup_viseron
from viseron.components.nvr.const import COMPONENT as NVR_COMPONENT
from viseron.const import LOADED

from tests.common import MockCamera


def test_setup_viseron_nvr_loaded(vis, caplog):
    """Test setup viseron when NVR is loaded."""
    vis.data[LOADED] = {NVR_COMPONENT: "Testing"}
    MockCamera(vis=vis, identifier="camera1")
    MockCamera(vis=vis, identifier="camera2")

    with (
        patch("viseron.Viseron", return_value=vis),
        patch("viseron.setup_components") as mocked_setup_components,
        patch("viseron.setup_domains") as mocked_setup_domains,
        patch("viseron.load_config", return_value="Testing") as mocked_load_config,
        patch("viseron.components.get_component"),
    ):
        setup_viseron(vis)

    mocked_setup_components.assert_called_once()
    mocked_setup_domains.assert_called_once()
    mocked_load_config.assert_called_once()
    assert (
        "Camera with identifier camera1 is not enabled under component nvr. "
        "This camera will not be processed" in caplog.text
    )
    assert (
        "Camera with identifier camera2 is not enabled under component nvr. "
        "This camera will not be processed" in caplog.text
    )
    caplog.clear()


def test_setup_viseron_nvr_missing(vis, caplog):
    """Test setup viseron when NVR is NOT loaded."""
    MockCamera(vis=vis, identifier="camera1")
    MockCamera(vis=vis, identifier="camera2")

    with (
        patch("viseron.Viseron", return_value=vis),
        patch("viseron.setup_components") as mocked_setup_components,
        patch("viseron.setup_component") as mocked_setup_component,
        patch("viseron.setup_domains") as mocked_setup_domains,
        patch("viseron.load_config", return_value="Testing") as mocked_load_config,
        patch("viseron.components.get_component"),
    ):
        setup_viseron(vis)

    mocked_setup_components.assert_called_once()
    mocked_setup_component.assert_called_once()
    mocked_setup_domains.assert_called_once()
    mocked_load_config.assert_called_once()
    assert (
        "Manually setting up component nvr with identifier camera1. "
        "Consider adding it your config.yaml instead" in caplog.text
    )
    assert (
        "Manually setting up component nvr with identifier camera2. "
        "Consider adding it your config.yaml instead" in caplog.text
    )
    caplog.clear()


def test_setup_viseron_cameras_missing(vis, caplog):
    """Test setup viseron when no cameras are loaded."""
    with (
        patch("viseron.Viseron", return_value=vis),
        patch("viseron.setup_components") as mocked_setup_components,
        patch("viseron.setup_component"),
        patch("viseron.setup_domains") as mocked_setup_domains,
        patch("viseron.load_config", return_value="Testing") as mocked_load_config,
        patch("viseron.components.get_component"),
    ):
        setup_viseron(vis)

    mocked_setup_components.assert_called_once()
    mocked_setup_domains.assert_called_once()
    mocked_load_config.assert_called_once()
    caplog.clear()


def test_setup_viseron_cameras_missing_nvr_loaded(vis, caplog):
    """Test setup viseron when no cameras are loaded but nvr is loaded."""
    vis.data[LOADED] = {NVR_COMPONENT: "Testing"}

    with (
        patch("viseron.Viseron", return_value=vis),
        patch("viseron.setup_components") as mocked_setup_components,
        patch("viseron.setup_component") as mocked_setup_component,
        patch("viseron.setup_domains") as mocked_setup_domains,
        patch("viseron.load_config", return_value="Testing") as mocked_load_config,
        patch("viseron.components.get_component"),
    ):
        setup_viseron(vis)

    mocked_setup_components.assert_called_once()
    mocked_setup_component.assert_not_called()
    mocked_setup_domains.assert_called_once()
    mocked_load_config.assert_called_once()
    caplog.clear()
