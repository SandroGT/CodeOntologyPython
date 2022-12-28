"""Generic utilities."""

from contextlib import contextmanager
from typing import Tuple, Type


@contextmanager
def pass_on_exception(exception_clause: Tuple[Type[Exception], ...] = (Exception,)):
    """When used in a `with` statement, creates a block in which a raised `Exception` just stops the execution of the
     current `with` block, but doesn't propagate to the upper scopes.

    Args:
        Tuple[E]: the tuple with all the `Exception` types we want to pass on.

    """
    try:
        yield
    except exception_clause:
        pass
