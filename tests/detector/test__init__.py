"""Tests for Detector."""
import sys
from contextlib import nullcontext

import pytest

from viseron.detector import import_object_detection
from viseron.exceptions import (
    DetectorConfigError,
    DetectorConfigSchemaError,
    DetectorImportError,
    DetectorModuleNotFoundError,
)

from tests.detector import (
    config_embedded,
    config_module_does_not_inherit,
    config_module_missing,
    config_module_schema_missing,
    config_separate,
    does_not_have_motion_class,
    does_not_inherit,
)


@pytest.mark.parametrize(
    "config, detector_module, raises",
    [
        ({"type": "config_embedded"}, config_embedded, nullcontext()),
        ({"type": "config_separate"}, config_separate, nullcontext()),
        (
            {"type": "does_not_exist"},
            None,
            pytest.raises(DetectorModuleNotFoundError),
        ),
        (
            {"type": "does_not_have_motion_class"},
            does_not_have_motion_class,
            pytest.raises(DetectorImportError),
        ),
        (
            {"type": "does_not_inherit"},
            does_not_inherit,
            pytest.raises(DetectorImportError),
        ),
        (
            {"type": "config_module_missing"},
            config_module_missing,
            pytest.raises(DetectorConfigError),
        ),
        (
            {"type": "config_module_does_not_inherit"},
            config_module_does_not_inherit,
            pytest.raises(DetectorConfigError),
        ),
        (
            {"type": "config_module_schema_missing"},
            config_module_schema_missing,
            pytest.raises(DetectorConfigSchemaError),
        ),
    ],
)
def test_import_motion_detection(config, detector_module, raises):
    """Test that dynamic import works."""
    if detector_module:
        sys.modules[f"viseron.detector.{config['type']}"] = detector_module

    with raises:
        import_object_detection(config)
