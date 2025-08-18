"""Jinja2 template helpers for Viseron."""
from __future__ import annotations

from numbers import Number
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from viseron import Viseron


class StateNamespace:
    """Namespace for accessing states in a domain-specific manner.

    This class allows access to states in templates by using dot notation,
    e.g., `states.binary_sensor.camera_1.state`.
    """

    def __init__(self, states_dict):
        self._states = states_dict

    def __getattr__(self, domain):
        """Return a domain-specific namespace for accessing states."""
        return _DomainNamespace(self._states, domain)

    def __getitem__(self, key):
        """Return a state by its key."""
        return self._states[key]


class _DomainNamespace:
    def __init__(self, states_dict, domain):
        self._states = states_dict
        self._domain = domain

    def __getattr__(self, entity):
        key = f"{self._domain}.{entity}"
        return self._states[key]

    def __getitem__(self, entity):
        key = f"{self._domain}.{entity}"
        return self._states[key]


def render_template(vis: Viseron, template_str: str | None, **kwargs) -> None | str:
    """Render a Jinja2 template with the states and any other arbitrary data."""
    if not template_str:
        return None
    states_ns = StateNamespace(vis.states.current)
    template = vis.jinja_env.from_string(template_str)
    return template.render(states=states_ns, **kwargs)


def _template_boolean(value: Any) -> bool:
    """Convert a rendered template value to a boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        value = value.lower().strip()
        if value in ("1", "true", "yes", "on", "enable"):
            return True
    elif isinstance(value, Number):
        # type ignore: https://github.com/python/mypy/issues/3186
        return value != 0  # type: ignore[comparison-overlap]
    return False


def render_template_condition(
    vis: Viseron, template_str: str | None, **kwargs
) -> tuple[Literal[False], None] | tuple[bool, str]:
    """Render a Jinja2 template condition.

    Returns True if the condition evaluates to a truthy value, otherwise False.
    Considers any number greater than 0 as truthy.
    """
    rendered_condition = render_template(vis, template_str, **kwargs)
    if rendered_condition is None:
        return False, rendered_condition
    try:
        if float(rendered_condition) > 0:
            return True, rendered_condition
    except (ValueError, TypeError):
        pass
    return (
        _template_boolean(rendered_condition),
        rendered_condition,
    )
