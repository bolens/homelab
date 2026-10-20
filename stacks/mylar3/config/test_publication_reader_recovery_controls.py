"""Actual public0644 sources, private copy only, no installed/live grant."""
import hashlib
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import os
import shutil
import subprocess
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
  writer=self.fixes/'media_writer.py';writer.write_bytes(b'# fixture Writer source\n');writer.chmod(0o644);self.writer=writer
  scope=self.fixes/'publication_native_configured_scope.py';scope.write_bytes(b'# fixture scope source\n');scope.chmod(0o644);self.scope=scope
  source=self.tree/'fixture.py';source.write_text('# fixture bytes\n');source.chmod(0o644);self.source=source
  (self.tree/'source-manifest.json').write_text(json.dumps(dict(version=1,files={'fixture.py':dict(sha256=digest(source))})));(self.tree/'source-manifest.json').chmod(0o644)
  (self.fixes/'publication_reader_cohort.json').write_text(json.dumps(dict(modules={'publication_reader_admission':dict(sha256=digest(module)),'publication_native_configured_scope':dict(sha256=digest(scope))},existing_sdk_closure={'media_writer':dict(tracked_source_sha256=digest(writer))})));(self.fixes/'publication_reader_cohort.json').chmod(0o644)
  for name in ('queue_control.py','worker_health.py'):
   path=self.fixes/name;path.write_text('# fixture native health '+name+'\n');path.chmod(0o644)
  (self.fixes/'standalone_control_sources.json').write_text(json.dumps([dict(path=name,sha256=digest(self.fixes/name)) for name in ('queue_control.py','worker_health.py')]))
 def copy(self):return m.copy_fixtures(self.fixes,self.stage)
 def test_public644_copy_private600_bytes_same(self):
  before={p: (p.read_bytes(),p.stat().st_mode,p.stat().st_ino) for p in (self.source,self.module,self.scope)};tree,_,_=self.copy();self.assertEqual((tree/'fixture.py').read_bytes(),self.source.read_bytes());self.assertEqual((tree/'fixture.py').stat().st_mode&511,0o600);self.assertEqual((tree.parent/'publication_reader_admission.py').stat().st_mode&511,0o600);self.assertEqual(before,{p:(p.read_bytes(),p.stat().st_mode,p.stat().st_ino) for p in before})
  self.assertEqual((tree.parent/'publication_native_configured_scope.py').read_bytes(),self.scope.read_bytes());self.assertEqual((tree.parent/'publication_native_configured_scope.py').stat().st_mode&511,0o600)
  for name in ('queue_control.py','worker_health.py'):
   self.assertEqual((tree.parent/name).read_bytes(),(self.fixes/name).read_bytes());self.assertEqual((tree.parent/name).stat().st_mode&511,0o600)
 def test_ignored_config_not_copied(self):
  (self.tree/'ignored-secret.ini').write_text('fixture only');tree,_,_=self.copy();self.assertFalse((tree/'ignored-secret.ini').exists())
 def test_unknown_source_hash_refused(self):
  self.source.write_bytes(b'foreign');self.assertRaises(m.Held,self.copy)
  # Keep the existing bad declared-file assertion, then exercise the genuine
  # finite canonical sibling independently in fresh disposable copy targets.
  self.source.write_text('# fixture bytes\n')
  cohort=self.fixes/'publication_reader_cohort.json';original=cohort.read_bytes()
  for bad in (None,'','g'*64):
   with self.subTest(scope_pin=bad):
    value=json.loads(original);value['modules']['publication_native_configured_scope']['sha256']=bad;cohort.write_text(json.dumps(value))
    with tempfile.TemporaryDirectory() as target,self.assertRaisesRegex(m.Held,'Explicit canonical scope source pin required'):m.copy_fixtures(self.fixes,target)
  cohort.write_bytes(original)
  for name in ('queue_control.py','worker_health.py'):
   path=self.fixes/name;before=path.read_bytes();path.write_bytes(b'foreign')
   with tempfile.TemporaryDirectory() as target,self.assertRaisesRegex(m.Held,'Source bytes or incarnation changed'):m.copy_fixtures(self.fixes,target)
   path.write_bytes(before)
  source_map=self.fixes/'standalone_control_sources.json';before=source_map.read_bytes();rows=json.loads(before)
  for changed in (rows[:1],rows+rows[:1],[dict(path=row['path'],sha256=None)for row in rows]):
   source_map.write_text(json.dumps(changed))
   with tempfile.TemporaryDirectory() as target,self.assertRaisesRegex(m.Held,'Explicit native health source pin required'):m.copy_fixtures(self.fixes,target)
  source_map.write_bytes(before)
  cohort.write_bytes(original);self.scope.write_bytes(b'foreign')
  with tempfile.TemporaryDirectory() as target,self.assertRaisesRegex(m.Held,'Source bytes or incarnation changed'):m.copy_fixtures(self.fixes,target)
  self.scope.unlink()
  with tempfile.TemporaryDirectory() as target,self.assertRaises(FileNotFoundError):m.copy_fixtures(self.fixes,target)
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
 def test_real588_public644_closure_passes_no_source_changes(self):
  # Exact current public files, no ignored config copied.
  actual=self.root/'actual';actual.mkdir();manifest=json.loads((PUBLIC/'reader_recovery/source-manifest.json').read_bytes());tree=actual/'reader_recovery';tree.mkdir()
  for name in manifest['files']:
   dst=tree/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(PUBLIC/'reader_recovery'/name,dst);dst.chmod(0o644)
  shutil.copyfile(PUBLIC/'reader_recovery/source-manifest.json',tree/'source-manifest.json')
  shutil.copyfile(PUBLIC/'media_writer.py',actual/'media_writer.py');(actual/'media_writer.py').chmod(0o644)
  for name in ('publication_reader_cohort.json','publication_reader_admission.py','publication_native_configured_scope.py','standalone_control_sources.json','queue_control.py','worker_health.py','publication_guard.py','publication_archive_layout.py','publication_archive_derivative.py','publication_archive_repair.py','tagger_metadata.py'):shutil.copyfile(PUBLIC/name,actual/name)
  before={str(p.relative_to(actual)):(digest(p),p.stat().st_mode,p.stat().st_ino) for p in actual.rglob('*') if p.is_file()};value=m.run(actual);self.assertEqual(value['tests'],1124);self.assertFalse(value['installed_factory_verified']);self.assertEqual(before,{str(p.relative_to(actual)):(digest(p),p.stat().st_mode,p.stat().st_ino) for p in actual.rglob('*') if p.is_file()})
 def parent(self):
  spec=importlib.util.spec_from_file_location('parent_runner',ROOT/'run_publication_reader_controls.py');parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
  (self.fixes/'publication_negative_namespace_kernel.py').write_text('# disposable budget fixture\n')
  return parent
 def test_aggregate_budget_encloses_actual_serial_child_deadlines(self):
  # Only process scheduling/results are projected; actual fixture-copy and
  # parent runner paths execute. This does not rerun or grant the 1124 controls.
  parent=self.parent();children=[];expected=dict(m.SUITES)
  def child(command,**kw):
   children.append(kw['timeout']);count=expected[Path(command[-1]).name]
   return subprocess.CompletedProcess(command,0,b'',('Ran %d tests in 0.01s\n\nOK\n'%count).encode())
  with patch.object(m.subprocess,'run',side_effect=child):value=m.run(self.fixes)
  self.assertEqual(value['tests'],1124);self.assertEqual(len(children),len(m.SUITES));self.assertEqual(len(m.SUITES),68);self.assertEqual(m.SUITES[-1],('test_genuine_reader_quiescence.py',18))
  calls=[]
  def scheduled(command,**kw):calls.append((Path(command[-1]).name,kw));return subprocess.CompletedProcess(command,0)
  with patch.object(parent,'FIXES',self.fixes),patch.object(parent.os,'geteuid',return_value=1000),patch.object(parent.subprocess,'run',side_effect=scheduled),contextlib.redirect_stdout(io.StringIO()):parent.main()
  self.assertEqual([name for name,_ in calls],list(parent.SUITES)+['run_reader_recovery_controls.py'])
  for name,kw in calls:
   self.assertTrue(kw['check'])
   if name in ('test_publication_reader_recovery_controls.py','run_reader_recovery_controls.py'):
    self.assertEqual(kw['timeout'],8220)
    self.assertGreaterEqual(kw['timeout'],sum(children)+60)
   else:self.assertEqual(kw['timeout'],90)
 def test_aggregate_timeout_still_propagates_before_following_proof(self):
  parent=self.parent();calls=[]
  def scheduled(command,**kw):
   name=Path(command[-1]).name;calls.append(name)
   if name=='test_publication_reader_recovery_controls.py':raise subprocess.TimeoutExpired(command,kw['timeout'])
   return subprocess.CompletedProcess(command,0)
  with patch.object(parent,'FIXES',self.fixes),patch.object(parent.os,'geteuid',return_value=1000),patch.object(parent.subprocess,'run',side_effect=scheduled),contextlib.redirect_stdout(io.StringIO()),self.assertRaises(subprocess.TimeoutExpired):parent.main()
  self.assertEqual(calls,list(parent.SUITES));self.assertNotIn('run_reader_recovery_controls.py',calls)
if __name__=='__main__':unittest.main()
