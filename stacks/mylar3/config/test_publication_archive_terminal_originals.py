"""Actual archive cap/Writer/SQLite. Host reader and SDK origins explicitly doubled."""
import os,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import test_publication_archive_adoption as base
a=base.a;o=base.o
class Export(unittest.TestCase):
 setUp=base.Tests.setUp
 lease=base.Tests.lease
 cap=base.Tests.cap
 def completed(self):
  cap=self.cap();cap.install();cap.complete();return cap
 def test_complete_live_export(self):
  cap=self.completed();handle=a.terminal_originals(cap);v=a.terminal_original_vectors(handle,cap)
  self.assertEqual(v['phase'],'complete');self.assertEqual(v['operation_id'],self.c.operation_id)
  self.assertIs(a.terminal_originals(cap),handle);self.assertEqual(dict(v['files'])[str(self.prep._operation)],tuple(self.prep._directory))
 def test_rollback_live_export(self):
  import test_publication_archive_rollback as rb
  cap=self.cap();cap.install();cap.reverse()
  with patch.object(rb.rollback,'installed'):rb.rollback.from_reversed(cap).clear()
  handle=a.terminal_originals(cap);v=a.terminal_original_vectors(handle,cap)
  self.assertEqual(v['phase'],'rollback-complete');self.assertEqual(v['receipt'][0],str(cap.journal/'rollback-complete.json'))
 def test_late_stage_samebytes_holds(self):
  cap=self.completed();handle=a.terminal_originals(cap);real=a._terminal_close;p=self.prep._operation/'preparation.json'
  def late(*args):
   real(*args);q=p.with_name('replacement');q.write_bytes(p.read_bytes());q.chmod(0o600);os.replace(q,p)
  with patch.object(a,'_terminal_close',late),self.assertRaises(o.Held):a.terminal_original_vectors(handle,cap)
 def test_late_namespace_holds(self):
  cap=self.completed();handle=a.terminal_originals(cap);real=a._terminal_close
  def late(*args):real(*args);(cap.journal/'foreign').write_bytes(b'foreign')
  with patch.object(a,'_terminal_close',late),self.assertRaises(o.Held):a.terminal_original_vectors(handle,cap)
 def test_last_helper_registry_mutation_holds(self):
  cap=self.completed();handle=a.terminal_originals(cap);real=a._terminal_close
  def late(*args):real(*args);args[1]['deadline']+=100
  with patch.object(a,'_terminal_close',late),self.assertRaises(o.Held):a.terminal_original_vectors(handle,cap)
 def physical_fault(self,kind):
  cap=self.completed();handle=a.terminal_originals(cap);real=a._terminal_close;listing=os.listdir;armed=[];fired=[]
  def close(*args):real(*args);armed.append(True)
  def late(path):
   result=listing(path)
   if armed and Path(path)==cap.root and not fired:
    if kind=='writer':self.c.writer.local[1].allow_pending=True
    elif kind=='phase':cap._phase='prepared'
    elif kind=='contents':cap._contents[next(iter(cap._contents))]='0'*64
    elif kind=='before':cap._before['foreign-core-field']='changed'
    else:a._TERMINAL_EXPORTS.pop(cap)
    fired.append(True)
   return result
  try:
   with patch.object(a,'_terminal_close',close),patch.object(a.os,'listdir',late),self.assertRaises(o.Held):a.terminal_original_vectors(handle,cap)
   self.assertTrue(fired)
  finally:self.c.writer.local[1].allow_pending=False
 def test_final_physical_writer_purpose_holds(self):self.physical_fault('writer')
 def test_final_physical_registry_removal_holds(self):self.physical_fault('registry')
 def test_final_physical_cap_phase_holds(self):self.physical_fault('phase')
 def test_final_physical_contents_core_holds(self):self.physical_fault('contents')
 def test_final_physical_catalog_core_holds(self):self.physical_fault('before')
 def test_dead_registry_holds(self):
  cap=self.completed();handle=a.terminal_originals(cap);a._TERMINAL_RECORDS.pop(handle)
  with self.assertRaises(o.Held):a.terminal_original_vectors(handle,cap)
 def test_incomplete_holds(self):
  with self.assertRaises(o.Held):a.terminal_originals(self.cap())
 def test_saved_json_not_export(self):
  cap=self.completed()
  with self.assertRaises(o.Held):a.terminal_original_vectors({'receipt':cap._receipt},cap)
 def test_wrong_cap_holds(self):
  cap=self.completed();handle=a.terminal_originals(cap)
  with self.assertRaises(o.Held):a.terminal_original_vectors(handle,object())
 def test_receipt_samebytes_replacement(self):
  cap=self.completed();handle=a.terminal_originals(cap);p=Path(cap._receipt['path']);q=p.with_name('foreign');q.write_bytes(p.read_bytes());q.chmod(0o600);os.replace(q,p)
  with self.assertRaises(o.Held):a.terminal_original_vectors(handle,cap)
 def test_late_final_helper_metadata_holds(self):
  cap=self.completed();handle=a.terminal_originals(cap);real=a._terminal_close;fired=[]
  def late(*args):
   real(*args);(self.prep._operation/'preparation.json').chmod(0o640);fired.append(True)
  with patch.object(a,'_terminal_close',late),self.assertRaises(o.Held):a.terminal_original_vectors(handle,cap)
  self.assertTrue(fired)
 def test_late_pending_holds(self):
  cap=self.completed();handle=a.terminal_originals(cap);real=a._terminal_close
  def late(*args):real(*args);(self.c.writer.root/'normalizer-v1.pending').write_bytes(b'foreign')
  with patch.object(a,'_terminal_close',late),self.assertRaises(o.Held):a.terminal_original_vectors(handle,cap)
 def test_late_writer_purpose_holds(self):
  cap=self.completed();handle=a.terminal_originals(cap);real=a._terminal_close
  def late(*args):real(*args);self.c.writer.local[1].allow_pending=True
  with patch.object(a,'_terminal_close',late),self.assertRaises(o.Held):a.terminal_original_vectors(handle,cap)
  self.c.writer.local[1].allow_pending=False
 def test_first_export_late_source_holds(self):
  cap=self.completed();real=a.installed;source=Path(a.__file__);old=source.stat().st_mode
  def late():real();source.chmod(0o640)
  try:
   with patch.object(a,'installed',late),self.assertRaises(o.Held):a.terminal_originals(cap)
  finally:source.chmod(old)
class Binding(unittest.TestCase):
 setUp=base.Tests.setUp
 lease=base.Tests.lease
 cap=base.Tests.cap
 def fixture(self,rollback=False):
  import copy,hashlib,sqlite3,types
  import test_publication_reader_lifecycle as life
  self.l=life.Tests('runTest');self.l.setUp();self.addCleanup(self.l.doCleanups);self.l.scope_patch.stop();self.m=life.m
  # Actual reader databases with production mapping spelling, captured before birth.
  for name in ('database.sqlite','tasks.sqlite'):
   with sqlite3.connect(self.cfg/name) as db:db.execute('UPDATE BOOK SET URL=?',('file:///data/library/'+self.c.source.name,))
   (self.restore/name).write_bytes((self.cfg/name).read_bytes())
  self.l.state['Mounts']=[{'Type':'bind','Source':str(self.c.library),'Destination':'/data/library'}]
  self.l.response['reader']=copy.deepcopy(self.l.state)
  self.l.reader.update(config_root=str(self.cfg),restore_root=str(self.restore),scratch=str(self.scratch),runtime=self.l.state,current_pairs=self.l.pairs(self.cfg),restore_pairs=self.l.pairs(self.restore))
  sdk=self.l.write('sdk.json',self.m.encoded({name:hashlib.sha256(Path(self.m.__file__).with_name(name).read_bytes()).hexdigest() for name in ('publication_reader_lifecycle.py','publication_archive_adoption.py','publication_archive_owned.py','publication_archive_reader.py','publication_native_configured_scope.py')}))
  self.l.input=self.l.write('input.json',self.m.encoded({'action':'archive-one','owner':self.c.owner,'operation_id':self.c.operation_id,'sdk_map':sdk}))
  self.l.doc.update(input_sha256=self.l.input['sha256'],command=['fixture','--phase','execute']);self.l.doc['proofs']['archive_sdk_map']=sdk;self.l.write('input.lifecycle.json',self.m.encoded(self.l.doc))
  self.life=self.m.StoppedReaderCustody(self.m._KEY,self.l.input['path'],self.l.input['sha256'],self.l.nonce,self.l.parent['sha256'],self.l.doc['command'],self.l.channel)
  case=self
  class Scope:
   def __init__(obj,c):obj._custody=c;obj.callback=None
   @property
   def binding(obj):return {'data':str(case.c.controller.root),'roots':[str(case.c.library)],'tool_root':str(case.c.controller.tool_root),'host_scopes':{'library':str(case.c.library)}}
   def vectors(obj):return {},{}
   def revalidate(obj):
    obj._custody.revalidate_stopped()
    if obj.callback:obj.callback()
  self.scope=Scope(self.life);sm=types.SimpleNamespace(__file__='/app/mylar3/mylar/publication_native_configured_scope.py',NativeConfiguredScope=Scope,from_checked_parent=lambda c:Scope(c))
  import importlib
  real=importlib.import_module
  pp=patch.object(self.m.importlib,'import_module',lambda name:sm if name=='mylar.publication_native_configured_scope' else real(name));pp.start();self.addCleanup(pp.stop)
  pp=patch.object(base.r,'lifecycle',return_value=self.m);pp.start();self.addCleanup(pp.stop)
  pp=patch.object(self.m,'_archive_terminal_components',return_value=(sm,o,a));pp.start();self.addCleanup(pp.stop)
  cap=self.cap();cap.install()
  if rollback:
   import test_publication_archive_rollback as rb
   cap.reverse()
   with patch.object(rb.rollback,'installed'):rb.rollback.from_reversed(cap).clear()
  else:cap.complete()
  return cap
 def test_same_custody_pipe_and_original_terminal_rows(self):
  cap=self.fixture();before=(self.life.channel,self.life.channel_seal,self.life.command,self.life.deadline,self.life.proofs.copy())
  self.assertIs(self.m.bind_archive_terminal_originals(self.life,self.scope,cap),self.life)
  self.assertEqual((self.life.channel,self.life.channel_seal,self.life.command,self.life.deadline,self.life.proofs),before)
  self.assertEqual(tuple(self.life.files[cap.journal/'baseline.json']),tuple(cap._files[cap.journal/'baseline.json']))
  self.assertIn(self.life,self.m._ARCHIVE_TERMINALS)
 def test_rollback_same_custody_and_verifier(self):
  cap=self.fixture(rollback=True);self.m.bind_archive_terminal_originals(self.life,self.scope,cap);v=base.load('publication_archive_verifier')
  with patch.object(v,'installed'):answer=v.verify_rollback_existing(self.c.controller,self.c.writer,self.life,cap.journal/'baseline.json',self.scratch)
  self.assertTrue(answer['native_preimage_restored']);self.assertFalse(answer['ordinary_import_grant'])
 def test_later_source_first_read_holds(self):
  cap=self.fixture();p=Path(self.m.__file__).with_name('publication_native_configured_scope.py');old=p.stat().st_mode;real=o.read_checked;fired=[]
  def late(*args):
   result=real(*args)
   if str(args[0]).endswith('publication_reader_lifecycle.py') and not fired:p.chmod(0o640);fired.append(True)
   return result
  try:
   with patch.object(o,'read_checked',late),self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
   self.assertTrue(fired)
  finally:p.chmod(old)
 def test_registry_callback_invalidates(self):
  cap=self.fixture();fired=[]
  def late():
   if self.life in self.m._ARCHIVE_TERMINALS and not fired:self.m._ARCHIVE_TERMINALS[self.life][3]['phase']='foreign';fired.append(True)
  self.scope.callback=late
  with self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
  self.assertTrue(fired)
 def complete_core_fault(self,kind):
  cap=self.fixture();real=self.m.require;listing=os.listdir;armed=[];fired=[]
  def required(value,reason):
   real(value,reason)
   if reason=='archive-terminal-same-original-lifetime':armed.append(True)
  def late(path):
   result=listing(path)
   if armed and Path(path)==cap.root and not fired:
    if kind=='contents':cap._contents[next(iter(cap._contents))]='0'*64
    else:cap._before['foreign-core-field']='changed'
    fired.append(True)
   return result
  with patch.object(self.m,'require',required),patch.object(self.m.os,'listdir',late),self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
  self.assertTrue(fired);self.assertNotIn(self.life,self.m._SEALS);self.assertNotIn(self.life,self.m._ARCHIVE_TERMINALS)
 def test_final_physical_contents_core_invalidates(self):self.complete_core_fault('contents')
 def test_final_physical_catalog_core_invalidates(self):self.complete_core_fault('before')
 def test_final_physical_cap_registry_invalidates(self):
  cap=self.fixture();real=self.m.require;listing=os.listdir;armed=[];fired=[]
  def required(value,reason):
   real(value,reason)
   if reason=='archive-terminal-same-original-lifetime':armed.append(True)
  def late(path):
   result=listing(path)
   if armed and Path(path)==cap.root and not fired:a._TERMINAL_EXPORTS.pop(cap);fired.append(True)
   return result
  with patch.object(self.m,'require',required),patch.object(self.m.os,'listdir',late),self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
  self.assertTrue(fired)
 def test_final_physical_pipe_drift_invalidates(self):
  cap=self.fixture();real=self.m.require;listing=os.listdir;armed=[];fired=[]
  def required(value,reason):
   real(value,reason)
   if reason=='archive-terminal-same-original-lifetime':armed.append(True)
  def late(path):
   result=listing(path)
   if armed and Path(path)==cap.root and not fired:self.life.channel.input,self.life.channel.output=self.life.channel.output,self.life.channel.input;fired.append(True)
   return result
  try:
   with patch.object(self.m,'require',required),patch.object(self.m.os,'listdir',late),self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
   self.assertTrue(fired)
  finally:
   if fired:self.life.channel.input,self.life.channel.output=self.life.channel.output,self.life.channel.input
 def test_last_require_pipe_drift_invalidates(self):
  cap=self.fixture();real=self.m.require;fired=[]
  def late(value,reason):
   real(value,reason)
   if reason=='archive-terminal-same-original-lifetime' and not fired:self.life.channel.input,self.life.channel.output=self.life.channel.output,self.life.channel.input;fired.append(True)
  with patch.object(self.m,'require',late),self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
  self.assertTrue(fired)
 def test_last_require_invocation_drift_invalidates(self):
  cap=self.fixture();real=self.m.require;fired=[]
  def late(value,reason):
   real(value,reason)
   if reason=='archive-terminal-same-original-lifetime' and not fired:self.life.invocation['operation_id']='foreign';fired.append(True)
  with patch.object(self.m,'require',late),self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
  self.assertTrue(fired)
 def test_original_pipe_drift_invalidates(self):
  cap=self.fixture();real=self.scope.revalidate;fired=[]
  def late():
   real()
   if self.life in self.m._ARCHIVE_TERMINALS and not fired:self.life.channel.seq=-1;self.life.channel.input,self.life.channel.output=self.life.channel.output,self.life.channel.input;fired.append(True)
  self.scope.revalidate=late
  with self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
  self.assertTrue(fired)
 def test_fresh_actual_verifier_after_bind(self):
  cap=self.fixture();self.m.bind_archive_terminal_originals(self.life,self.scope,cap);v=base.load('publication_archive_verifier')
  with patch.object(v,'installed'):answer=v.verify_existing(self.c.controller,self.c.writer,self.life,cap.journal/'baseline.json',self.scratch)
  self.assertTrue(answer['reader_reference_preservation']);self.assertFalse(answer['ordinary_import_grant'])
 def test_final_custody_helper_target_holds(self):
  cap=self.fixture();real=self.life._sealed;fired=[]
  def late(*args):
   result=real(*args)
   if self.life in self.m._ARCHIVE_TERMINALS and not fired:self.c.source.chmod(0o640);fired.append(True)
   return result
  with patch.object(self.life,'_sealed',late),self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
  self.assertTrue(fired)
 def test_late_source_map_replacement_holds(self):
  cap=self.fixture();real=self.scope.revalidate;fired=[];p=Path(self.life.invocation['sdk_map']['path'])
  def late():
   real()
   if self.life in self.m._ARCHIVE_TERMINALS and not fired:
    q=p.with_name('replaced');q.write_bytes(p.read_bytes());q.chmod(0o600);os.replace(q,p);fired.append(True)
  self.scope.revalidate=late
  with self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
  self.assertTrue(fired)
 def test_missing_sdk_component_holds(self):
  cap=self.fixture();p=Path(self.life.invocation['sdk_map']['path']);p.write_bytes(b'{}')
  with self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
 def test_unknown_invocation_holds(self):
  cap=self.fixture();self.life.invocation['owner']['issueid']='foreign'
  with self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
 def test_receipt_json_cannot_bind(self):
  cap=self.fixture()
  with self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap._receipt)
 def test_one_use(self):
  cap=self.fixture();self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
  with self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
 def test_wrong_original_custody(self):
  cap=self.fixture();self.scope._custody=object()
  with self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
 def test_late_scope_metadata_invalidates(self):
  cap=self.fixture();fired=[]
  def late():
   if self.life in self.m._ARCHIVE_TERMINALS and not fired:(self.prep._operation/'preparation.json').chmod(0o640);fired.append(True)
  self.scope.callback=late
  with self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
  self.assertTrue(fired)
  with self.assertRaises(self.m.Held):self.life.revalidate_stopped()
 def test_late_scope_pending_invalidates(self):
  cap=self.fixture();fired=[]
  def late():
   if self.life in self.m._ARCHIVE_TERMINALS and not fired:(self.c.writer.root/'normalizer-v1.pending').write_bytes(b'foreign');fired.append(True)
  self.scope.callback=late
  with self.assertRaises(self.m.Held):self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
  self.assertTrue(fired)
if __name__=='__main__':unittest.main()
