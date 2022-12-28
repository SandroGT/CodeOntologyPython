"""Generic utilities."""

from contextlib import contextmanager


@contextmanager
def pass_on_exception():
    """When used in a `with` statement, creates a block in which a raised Exception just stop the execution of the
     current `with` block, but doesn't propagate to the upper scopes, just "passing on the Exception".

    """
    try:
        yield
    except Exception:
        pass
