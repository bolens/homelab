"""Canonical package alias; creates no reader class or transaction authority."""
import importlib
from pathlib import Path
_phase=importlib.import_module('mylar.publication_reader_phase')
_path=Path(_phase.__file__)
if _path.parent!=Path('/app/mylar3/mylar') or _path.resolve()!=_path:
    raise RuntimeError('installed reader SQL body required')
sql_five_transition=_phase.sql_five_transition
