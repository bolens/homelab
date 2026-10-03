"""Serialize native readers/writers and recover publication before admission."""
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
import threading
from .media_writer import Writer

_LOCAL = threading.local()


def active():
    return bool(getattr(_LOCAL, 'depth', 0))


def owner():
    import mylar
    return Writer(Path(mylar.DATA_DIR)/'media-writer', create=False)


@contextmanager
def operation(*, reconcile=False):
    from . import tagger_native
    writer = owner()
    with writer.hold(allow_tagger_pending=True, allow_release_pending=True, timeout=180):
        outer = not getattr(_LOCAL, 'depth', 0)
        if outer and (reconcile or writer.fenced(tagger=True)):
            tagger_native.recover(writer)
        if outer and writer.fenced(release=True):
            from . import release_naming
            release_naming.recover(writer)
        _LOCAL.depth = getattr(_LOCAL, 'depth', 0) + 1
        try:
            yield writer
        finally:
            _LOCAL.depth -= 1
            if outer and writer.fenced(tagger=True):
                tagger_native.recover(writer)


def initialize():
    import mylar
    Writer(Path(mylar.DATA_DIR)/'media-writer', create=True)
    with operation(reconcile=True):
        pass


def guard(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with operation():
            return function(*args, **kwargs)
    return wrapped
