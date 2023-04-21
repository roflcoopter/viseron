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

    def __init__(  # pylint: disable=dangerous-default-value
        self,
        identifier="test_camera_identifier",
        resolution=(1920, 1080),
        extension="mp4",
        access_tokens=["test_access_token", "test_access_token_2"],
        **kwargs,
    ):
        """Initialize the mock camera."""
        super().__init__(
            recorder=MagicMock(),
            identifier=identifier,
            resolution=resolution,
            extension=extension,
            access_tokens=access_tokens,
            **kwargs,
        )


def return_any(cls):
    """Mock any return value."""

    class Any(cls):
        """Mock any return value."""

        def __eq__(self, other):
            return True

    return Any()
