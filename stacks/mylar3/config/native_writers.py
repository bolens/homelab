"""Serialize native post-processing and complete manual tagging with the worker."""
from functools import wraps
from pathlib import Path
from .media_writer import Writer


def owner():
    import mylar
    return Writer(Path(mylar.DATA_DIR)/'media-writer',create=False)


def initialize():
    import mylar
    Writer(Path(mylar.DATA_DIR)/'media-writer',create=True)


def guard(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        with owner().hold(timeout=180):
            return function(*args,**kwargs)
    return wrapped
