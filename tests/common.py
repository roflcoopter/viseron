"""Common mocks for Viseron tests."""


from unittest.mock import MagicMock


class MockComponent:
    """Representation of a fake component."""

    def __init__(self, component, setup_component=None):
        """Initialize the mock component."""
        self.__name__ = f"viseron.components.{component}"
        self.__file__ = f"viseron/components/{component}"

        self.name = component
        if setup_component is not None:
            self.setup_component = setup_component


class MockCamera(MagicMock):
    """Representation of a fake camera."""

    def __init__(self, identifier="test_camera_identifier", resolution=(1920, 1080)):
        """Initialize the mock component."""
        super().__init__(
            recorder=MagicMock(), identifier=identifier, resolution=resolution
        )


def return_any(cls):
    """Mock any return value."""

    class Any(cls):
        """Mock any return value."""

        def __eq__(self, other):
            return True

    return Any()
