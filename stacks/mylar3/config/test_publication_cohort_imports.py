"""Canonical package identity only; no installed origin or authority grant."""
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parent
class Controls(unittest.TestCase):
 def test_successor_canonical_package_identity(self):
  code="""import types,sys,importlib
from pathlib import Path
p=types.ModuleType('mylar');p.__path__=[sys.argv[1]];sys.modules['mylar']=p
n=importlib.import_module('mylar.publication_negative');a=importlib.import_module('mylar.publication_api');g=importlib.import_module('mylar.publication_guard');w=importlib.import_module('mylar.media_writer');u=importlib.import_module('mylar.publication_mutation');c=importlib.import_module('mylar.publication_negative_catalog')
assert n.guard is a.guard is g and n.mutation is u and n.catalog is c and a.Writer is w.Writer
assert 'publication_guard' not in sys.modules and 'publication_mutation' not in sys.modules
r=importlib.import_module('mylar.publication_reader_admission');l=importlib.import_module('mylar.publication_reader_lifecycle')
import hashlib
assert r.PARENT_SHA is None and r.NEGATIVE_SHA==hashlib.sha256(Path(n.__file__).read_bytes()).hexdigest() and r.LIFECYCLE_SHA==hashlib.sha256(Path(l.__file__).read_bytes()).hexdigest()
"""
  subprocess.run([sys.executable,'-c',code,str(ROOT)],check=True)
 def test_exact_installed_origins_remain_required(self):
  code="""import types,sys,importlib
p=types.ModuleType('mylar');p.__path__=[sys.argv[1]];sys.modules['mylar']=p
for name,reason in [('publication_reader_disk','installed checked reader kernel'),('publication_reader_sql_transition','installed reader SQL body required')]:
 try:importlib.import_module('mylar.'+name)
 except RuntimeError as error:assert str(error)==reason
 else:raise AssertionError('host fixture must not receive installed-origin grant')
"""
  subprocess.run([sys.executable,'-c',code,str(ROOT)],check=True)
if __name__=='__main__':unittest.main()
