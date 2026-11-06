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

class ProtectedImageSources(unittest.TestCase):
 def fixture(self, root):
  import importlib.util,os
  spec=importlib.util.spec_from_file_location('protected_sources',ROOT/'protected_image_sources.py')
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  for name in module.PROTECTED_FILES:(root/name).write_bytes(('source:'+name).encode())
  return module,os.geteuid()
 def test_group_writable_api_refused_then_normalized_without_byte_changes(self):
  with tempfile.TemporaryDirectory()as folder:
   root=Path(folder);module,owner=self.fixture(root);path=root/'api.py';path.chmod(0o664)
   before={p.name:p.read_bytes()for p in root.iterdir()}
   with self.assertRaises(AssertionError):module.inspect_sources(root,owner=owner)
   rows=module.inspect_sources(root,normalize=True,owner=owner)
   self.assertEqual(set(rows),set(module.PROTECTED_FILES));self.assertEqual(before,{p.name:p.read_bytes()for p in root.iterdir()})
   self.assertTrue(all((root/n).stat().st_mode&0o777==0o644 for n in rows))
   self.assertEqual(rows,module.inspect_sources(root,owner=owner))
 def test_symlink_and_hardlink_refuse_before_normalization(self):
  import os
  for linked in ('symlink','hardlink'):
   with self.subTest(linked=linked),tempfile.TemporaryDirectory()as folder:
    root=Path(folder);module,owner=self.fixture(root);api=root/'api.py';api.chmod(0o664);last=root/module.PROTECTED_FILES[-1];last.unlink()
    if linked=='symlink':last.symlink_to(api)
    else:os.link(api,last)
    with self.assertRaises(AssertionError):module.inspect_sources(root,normalize=True,owner=owner)
    self.assertEqual(api.stat().st_mode&0o777,0o664)
 def test_foreign_owner_refuses_without_chmod(self):
  with tempfile.TemporaryDirectory()as folder:
   root=Path(folder);module,owner=self.fixture(root);path=root/'api.py';path.chmod(0o664)
   with self.assertRaises(AssertionError):module.inspect_sources(root,normalize=True,owner=owner+1)
   self.assertEqual(path.stat().st_mode&0o777,0o664)
 def test_metadata_drift_during_read_refuses(self):
  import os
  with tempfile.TemporaryDirectory()as folder:
   root=Path(folder);module,owner=self.fixture(root);path=root/'api.py';original=os.pread;changed=[]
   def read(fd,size,offset):
    raw=original(fd,size,offset)
    if not changed:path.chmod(0o664);changed.append(True)
    return raw
   with patch.object(module.os,'pread',side_effect=read),self.assertRaises(AssertionError):module.inspect_sources(root,owner=owner)
 def test_later_reused_descriptor_is_never_chmodded(self):
  import os
  with tempfile.TemporaryDirectory()as folder:
   parent=Path(folder);root=parent/'sources';root.mkdir();module,owner=self.fixture(root)
   (root/'api.py').chmod(0o664);later=root/'native_writers.py';later.chmod(0o664)
   foreign=parent/'foreign';foreign.write_bytes(b'foreign');foreign.chmod(0o664);original=os.fchmod;reused=[]
   def chmod(fd,mode):
    original(fd,mode)
    if not reused:
     for value in os.listdir('/proc/self/fd'):
      try:
       if os.readlink('/proc/self/fd/'+value)==str(later):target=int(value);break
      except OSError:continue
     source=os.open(foreign,os.O_RDONLY)
     try:os.dup2(source,target)
     finally:os.close(source)
     reused.append(target)
   try:
    with patch.object(module.os,'fchmod',side_effect=chmod),self.assertRaises(AssertionError):module.inspect_sources(root,normalize=True,owner=owner)
    self.assertEqual(foreign.stat().st_mode&0o777,0o664);self.assertEqual(foreign.read_bytes(),b'foreign')
   finally:
    for fd in reused:os.close(fd)
 def test_readonly_later_leaf_cannot_be_rebound_after_prior_read(self):
  import os
  with tempfile.TemporaryDirectory()as folder:
   root=Path(folder);module,owner=self.fixture(root);api=root/'api.py';inode=api.stat().st_ino;original=os.pread;calls=[]
   def read(fd,size,offset):
    raw=original(fd,size,offset)
    if os.fstat(fd).st_ino==inode:
     calls.append(True)
     if len(calls)==2:(root/'native_writers.py').chmod(0o444)
    return raw
   with patch.object(module.os,'pread',side_effect=read),self.assertRaises(AssertionError):module.inspect_sources(root,owner=owner)
 def test_final_read_metadata_change_refuses(self):
  import os
  with tempfile.TemporaryDirectory()as folder:
   root=Path(folder);module,owner=self.fixture(root);api=root/'api.py';inode=api.stat().st_ino;original=os.pread;calls=[]
   def read(fd,size,offset):
    raw=original(fd,size,offset)
    if os.fstat(fd).st_ino==inode:
     calls.append(True)
     if len(calls)==3:api.chmod(0o664)
    return raw
   with patch.object(module.os,'pread',side_effect=read),self.assertRaises(AssertionError):module.inspect_sources(root,owner=owner)
   self.assertEqual(len(calls),3)
 def test_final_read_ancestor_change_refuses(self):
  import os
  with tempfile.TemporaryDirectory()as folder:
   parent=Path(folder);root=parent/'sources';root.mkdir();module,owner=self.fixture(root);inode=(root/'api.py').stat().st_ino;original=os.pread;calls=[]
   def read(fd,size,offset):
    raw=original(fd,size,offset)
    if os.fstat(fd).st_ino==inode:
     calls.append(True)
     if len(calls)==3:parent.chmod(0o750)
    return raw
   with patch.object(module.os,'pread',side_effect=read),self.assertRaises(AssertionError):module.inspect_sources(root,owner=owner)
 def test_cleanup_preserves_primary_on_python_without_add_note(self):
  import io,os
  class LegacyError(RuntimeError):add_note=None
  with tempfile.TemporaryDirectory()as folder:
   root=Path(folder);module,owner=self.fixture(root);original=os.close
   def close(fd):original(fd);raise OSError('secondary-close')
   with patch.object(module.os,'pread',side_effect=LegacyError('original-read')),patch.object(module.os,'close',side_effect=close),patch.object(module.sys,'stderr',io.StringIO()),self.assertRaisesRegex(LegacyError,'original-read'):
    module.inspect_sources(root,owner=owner)
 def test_unrelated_ancestor_namespace_churn_is_not_source_drift(self):
  import os
  with tempfile.TemporaryDirectory()as folder:
   parent=Path(folder);root=parent/'sources';root.mkdir();module,owner=self.fixture(root);original=os.pread;changed=[]
   def read(fd,size,offset):
    raw=original(fd,size,offset)
    if not changed:(parent/'unrelated').write_bytes(b'fixture');changed.append(True)
    return raw
   with patch.object(module.os,'pread',side_effect=read):self.assertEqual(len(module.inspect_sources(root,owner=owner)),5)
 def test_symlinked_root_refuses(self):
  with tempfile.TemporaryDirectory()as folder:
   parent=Path(folder);root=parent/'root';root.mkdir();module,owner=self.fixture(root);link=parent/'alias';link.symlink_to(root,target_is_directory=True)
   with self.assertRaises(AssertionError):module.inspect_sources(link,owner=owner)

if __name__=='__main__':unittest.main()
