"""Test Viseron."""

from unittest.mock import MagicMock, patch

from viseron import setup_viseron
from viseron.components import Component, DomainToSetup
from viseron.components.nvr.const import (
    COMPONENT as NVR_COMPONENT,
    DOMAIN as NVR_DOMAIN,
)
from viseron.components.storage.const import COMPONENT as STORAGE_COMPOMEMT
from viseron.const import DOMAINS_TO_SETUP, LOADED
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN


def test_setup_viseron_nvr_loaded(vis, caplog):
    """Test setup viseron when NVR is loaded."""
    data = {
        STORAGE_COMPOMEMT: MagicMock(),
        LOADED: {NVR_COMPONENT: "Testing"},
        DOMAINS_TO_SETUP: {
            CAMERA_DOMAIN: {
                "camera1": DomainToSetup(
                    Component(vis, "test_component", "test_component", {}),
                    CAMERA_DOMAIN,
                    {},
                    "camera1",
                    [],
                    [],
                ),
                "camera2": "Testing",
            },
            NVR_DOMAIN: {},
        },
    }
    mocked_viseron = MagicMock(data=data)

    with patch("viseron.Viseron", return_value=mocked_viseron):
        with patch("viseron.setup_components") as mocked_setup_components:
            with patch("viseron.setup_domains") as mocked_setup_domains:
                with patch("viseron.load_config") as mocked_load_config:
                    mocked_load_config.return_value = "Testing"
                    with patch("viseron.components.get_component"):
                        setup_viseron()

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
    data = {
        STORAGE_COMPOMEMT: MagicMock(),
        LOADED: {},
        DOMAINS_TO_SETUP: {
            CAMERA_DOMAIN: {
                "camera1": DomainToSetup(
                    Component(vis, "test_component", "test_component", {}),
                    CAMERA_DOMAIN,
                    {},
                    "camera1",
                    [],
                    [],
                ),
                "camera2": "Testing",
            },
            NVR_DOMAIN: {},
        },
    }
    mocked_viseron = MagicMock(data=data)

    with patch("viseron.Viseron", return_value=mocked_viseron):
        with patch("viseron.setup_components") as mocked_setup_components:
            with patch("viseron.setup_component") as mocked_setup_component:
                with patch("viseron.setup_domains") as mocked_setup_domains:
                    with patch("viseron.load_config") as mocked_load_config:
                        mocked_load_config.return_value = "Testing"
                        with patch("viseron.components.get_component"):
                            setup_viseron()

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


def test_setup_viseron_cameras_missing(caplog):
    """Test setup viseron when no cameras are loaded."""
    data = {
        STORAGE_COMPOMEMT: MagicMock(),
        LOADED: {},
        DOMAINS_TO_SETUP: {},
    }
    mocked_viseron = MagicMock(data=data)

    with patch("viseron.Viseron", return_value=mocked_viseron):
        with patch("viseron.setup_components") as mocked_setup_components:
            with patch("viseron.setup_component") as mocked_setup_component:
                with patch("viseron.setup_domains") as mocked_setup_domains:
                    with patch("viseron.load_config") as mocked_load_config:
                        mocked_load_config.return_value = "Testing"
                        with patch("viseron.components.get_component"):
                            setup_viseron()

    mocked_setup_components.assert_called_once()
    mocked_setup_component.assert_not_called()
    mocked_setup_domains.assert_called_once()
    mocked_load_config.assert_called_once()
    caplog.clear()


def test_setup_viseron_cameras_missing_nvr_loaded(caplog):
    """Test setup viseron when no cameras are loaded but nvr is loaded."""
    data = {
        STORAGE_COMPOMEMT: MagicMock(),
        LOADED: {NVR_COMPONENT: "Testing"},
        DOMAINS_TO_SETUP: {},
    }
    mocked_viseron = MagicMock(data=data)

    with patch("viseron.Viseron", return_value=mocked_viseron):
        with patch("viseron.setup_components") as mocked_setup_components:
            with patch("viseron.setup_component") as mocked_setup_component:
                with patch("viseron.setup_domains") as mocked_setup_domains:
                    with patch("viseron.load_config") as mocked_load_config:
                        mocked_load_config.return_value = "Testing"
                        with patch("viseron.components.get_component"):
                            setup_viseron()

    mocked_setup_components.assert_called_once()
    mocked_setup_component.assert_not_called()
    mocked_setup_domains.assert_called_once()
    mocked_load_config.assert_called_once()
    caplog.clear()
