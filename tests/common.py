"""Common mocks for Viseron tests."""


class MockComponent:
    """Representation of a fake component."""

    def __init__(self, component, setup_component=None):
        """Initialize the mock component."""
        self.__name__ = f"viseron.components.{component}"
        self.__file__ = f"viseron/components/{component}"

        self.name = component
        if setup_component is not None:
            self.setup_component = setup_component


def return_any(cls):
    """Mock any return value."""

    class Any(cls):
        """Mock any return value."""

        def __eq__(self, other):
            return True

    return Any()
