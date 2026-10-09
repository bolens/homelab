"""Actual public0644 sources, private copy only, no installed/live grant."""
import hashlib
import importlib.util
import json
from pathlib import Path
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('private_runner',ROOT/'run_reader_recovery_controls.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
PUBLIC=Path(os.environ.get('MYLAR_READER_PUBLIC_FIXES',str(ROOT)))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class Controls(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.fixes=self.root/'public';self.fixes.mkdir();self.tree=self.fixes/'reader_recovery';self.tree.mkdir();self.stage=self.root/'private';self.stage.mkdir(mode=0o700)
  module=self.fixes/'publication_reader_admission.py';module.write_text('# fixture canonical disabled admission\n');module.chmod(0o644)
  self.module=module
  source=self.tree/'fixture.py';source.write_text('# fixture bytes\n');source.chmod(0o644);self.source=source
  (self.tree/'source-manifest.json').write_text(json.dumps(dict(version=1,files={'fixture.py':dict(sha256=digest(source))})));(self.tree/'source-manifest.json').chmod(0o644)
  (self.fixes/'publication_reader_cohort.json').write_text(json.dumps(dict(modules={'publication_reader_admission':dict(sha256=digest(module))})));(self.fixes/'publication_reader_cohort.json').chmod(0o644)
 def copy(self):return m.copy_fixtures(self.fixes,self.stage)
 def test_public644_copy_private600_bytes_same(self):
  before={p: (p.read_bytes(),p.stat().st_mode,p.stat().st_ino) for p in (self.source,self.module)};tree,_,_=self.copy();self.assertEqual((tree/'fixture.py').read_bytes(),self.source.read_bytes());self.assertEqual((tree/'fixture.py').stat().st_mode&511,0o600);self.assertEqual((tree.parent/'publication_reader_admission.py').stat().st_mode&511,0o600);self.assertEqual(before,{p:(p.read_bytes(),p.stat().st_mode,p.stat().st_ino) for p in before})
 def test_ignored_config_not_copied(self):
  (self.tree/'ignored-secret.ini').write_text('fixture only');tree,_,_=self.copy();self.assertFalse((tree/'ignored-secret.ini').exists())
 def test_unknown_source_hash_refused(self):
  self.source.write_bytes(b'foreign');self.assertRaises(m.Held,self.copy)
 def test_source_link_refused(self):
  self.source.rename(self.root/'saved');self.source.symlink_to(self.root/'saved');self.assertRaises(m.Held,self.copy)
 def test_unsafe_manifest_path_refused(self):
  (self.tree/'source-manifest.json').write_text(json.dumps(dict(version=1,files={'../escape.py':dict(sha256='a'*64)})));self.assertRaisesRegex(m.Held,'Unsafe fixture path',self.copy);self.assertFalse((self.stage/'escape.py').exists())
 def test_last_copy_readback_callback_originalmode_refused(self):
  real=Path.read_bytes;fired=[]
  def changed(p):
   raw=real(p)
   if p==self.stage/'config/publication_reader_admission.py':self.source.chmod(0o640);fired.append(True)
   return raw
  with patch.object(Path,'read_bytes',new=changed),self.assertRaisesRegex(m.Held,'Original source file drift'):self.copy()
  self.assertTrue(fired)
 def test_late_child_callback_originalbyte_drift_refused(self):
  # A real isolated trivial suite mutates only this synthetic source.
  script=self.tree/'test_stub.py';script.write_text("from pathlib import Path\nimport unittest\nclass T(unittest.TestCase):\n def test_one(self):Path("+repr(str(self.source))+ ").write_bytes(b'foreign')\nif __name__=='__main__':unittest.main()\n");manifest=json.loads((self.tree/'source-manifest.json').read_text());manifest['files']['test_stub.py']={'sha256':digest(script)};(self.tree/'source-manifest.json').write_text(json.dumps(manifest))
  with patch.object(m,'SUITES',(('test_stub.py',1),)),self.assertRaisesRegex(m.Held,'Original source file drift'):m.run(self.fixes)
 def test_real493_public644_closure_passes_no_source_changes(self):
  # Exact current public files, no ignored config copied.
  actual=self.root/'actual';actual.mkdir();manifest=json.loads((PUBLIC/'reader_recovery/source-manifest.json').read_bytes());tree=actual/'reader_recovery';tree.mkdir()
  for name in manifest['files']:
   dst=tree/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(PUBLIC/'reader_recovery'/name,dst);dst.chmod(0o644)
  shutil.copyfile(PUBLIC/'reader_recovery/source-manifest.json',tree/'source-manifest.json')
  for name in ('publication_reader_cohort.json','publication_reader_admission.py'):shutil.copyfile(PUBLIC/name,actual/name)
  before={str(p.relative_to(actual)):(digest(p),p.stat().st_mode,p.stat().st_ino) for p in actual.rglob('*') if p.is_file()};value=m.run(actual);self.assertEqual(value['tests'],493);self.assertFalse(value['installed_factory_verified']);self.assertEqual(before,{str(p.relative_to(actual)):(digest(p),p.stat().st_mode,p.stat().st_ino) for p in actual.rglob('*') if p.is_file()})
if __name__=='__main__':unittest.main()
