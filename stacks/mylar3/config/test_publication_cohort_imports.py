"""Canonical package identity only; no installed origin or authority grant."""
from pathlib import Path
import subprocess
import sys
import unittest
import hashlib
import tempfile
from unittest.mock import patch
from verify_publication_reader_cohort import verify_required_sdk
ROOT=Path(__file__).resolve().parent
class Controls(unittest.TestCase):
 def sdk_fixture(self,root):
  names=['pack_intake.py','media_writer.py'];pins={}
  for name in names:
   raw=(ROOT/name).read_bytes();(root/name).write_bytes(raw);pins[name]=hashlib.sha256(raw).hexdigest()
  return dict(required_sdk_names=names,base_installed_sources=pins)
 def test_required_sdk_checks_actual_bytes_and_rejects_stale_pin(self):
  with tempfile.TemporaryDirectory()as folder:
   root=Path(folder);base=self.sdk_fixture(root)
   self.assertEqual(verify_required_sdk(root,base),2)
   base['base_installed_sources']['pack_intake.py']='8e544c6ad5936f09d9cb895a511198d1c5eb283bebadd68e3907cd7bfebacb89'
   with self.assertRaises(AssertionError):verify_required_sdk(root,base)
 def test_required_sdk_refuses_symlink_even_when_bytes_match(self):
  with tempfile.TemporaryDirectory()as folder:
   root=Path(folder);base=self.sdk_fixture(root);path=root/'pack_intake.py'
   path.unlink();path.symlink_to(ROOT/'pack_intake.py')
   with self.assertRaises(AssertionError):verify_required_sdk(root,base)
 def test_required_sdk_preserves_original_mode_and_refuses_mode_drift(self):
  with tempfile.TemporaryDirectory()as folder:
   root=Path(folder);path=root/'__init__.py';raw=b'# upstream SDK fixture\n';path.write_bytes(raw);path.chmod(0o664)
   base=dict(required_sdk_names=[path.name],base_installed_sources={path.name:hashlib.sha256(raw).hexdigest()})
   self.assertEqual(verify_required_sdk(root,base),1);self.assertEqual(path.stat().st_mode&0o777,0o664)
   import os
   original=os.read;changed=[]
   def read(fd,size):
    value=original(fd,size)
    if not changed:path.chmod(0o644);changed.append(True)
    return value
   with patch('verify_publication_reader_cohort.os.read',side_effect=read),self.assertRaises(AssertionError):verify_required_sdk(root,base)
   self.assertEqual(changed,[True])
 def test_required_sdk_refuses_empty_duplicate_or_escaping_membership(self):
  with tempfile.TemporaryDirectory()as folder:
   root=Path(folder);base=self.sdk_fixture(root)
   for names in ([],['pack_intake.py','pack_intake.py'],['../pack_intake.py']):
    bad=dict(base,required_sdk_names=names)
    bad['base_installed_sources']=dict(base['base_installed_sources'],**{name:'0'*64 for name in names if name not in base['base_installed_sources']})
    with self.subTest(names=names),self.assertRaises(AssertionError):verify_required_sdk(root,bad)
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
