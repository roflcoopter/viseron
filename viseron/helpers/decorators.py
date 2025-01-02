"""Decorators for Viseron."""


from functools import wraps


def return_copy(func):
    """Call copy() on the function's return value."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return result.copy()

    return wrapper
