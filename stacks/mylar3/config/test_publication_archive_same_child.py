"""Real cap/SQLite/archive/Writer and OS pipe; host scope/origins explicit fixtures.

Canonical image and selected Docker child protocol acceptance remain root gates.
"""
import os
import threading
import tempfile
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch
import unittest
sys.path.insert(0,str(Path(__file__).parent))
import test_publication_archive_terminal_originals as fixture
base=fixture.base;o=fixture.o;a=fixture.a
history=base.load('publication_archive_history')
verifier=base.load('publication_archive_verifier')

class Tests(fixture.Binding):
 def cap(self):
  if not hasattr(self,'history_initialized'):
   history.initialize(self.c.controller,self.c.writer);self.history_initialized=True
  return super().cap()
 def live(self,reverse=False):
  cap=self.fixture(rollback=reverse)
  pp=patch.dict(sys.modules,{'mylar.publication_reader_lifecycle':self.m});pp.start();self.addCleanup(pp.stop)
  self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
  return cap
 def observe(self,cap,reverse=False):
  # Bind the actual host-loaded verifier's origin shim explicitly; earlier
  # inherited controls may reload it, so no cached fixture identity is assumed.
  with patch.dict(sys.modules,{'mylar.publication_archive_verifier':verifier}),patch.object(sys.modules['mylar'],'publication_archive_verifier',verifier,create=True),patch.object(verifier,'installed'):
   return history.observe_terminal(self.c.controller,self.c.writer,self.life,self.scope,self.c.owner,self.c.operation_id,cap.journal/'baseline.json',self.scratch,rollback=reverse,with_vectors=True,live_cap=cap)
 def test_live_query_preserves_registered_originals(self):
  cap=self.live();answer=self.m.archive_terminal_original_vectors(self.life,self.scope,cap)
  self.assertEqual(answer['terminal']['phase'],'complete');self.assertIs(self.life.channel,self.l.channel)
  self.assertIn(str(self.prep._operation),dict(answer['custody_originals']['files9']))
 def test_genuine_forward_fresh_verifier_history(self):
  cap=self.live();execute=history.executed(cap);answer=self.observe(cap)
  self.assertTrue(answer['summary']['reader_reference_preservation']);self.assertFalse(answer['summary']['ordinary_import_grant'])
  self.assertEqual(history.decode(Path(answer['history']['path']).read_bytes())['kind'],'terminal-observed')
  self.assertIn(execute['path'],dict(answer['original_vectors']['files9']))
 def test_genuine_rollback_fresh_verifier_history(self):
  cap=self.live(True);history.executed(cap);answer=self.observe(cap,True)
  self.assertTrue(answer['summary']['native_preimage_restored']);self.assertFalse(answer['summary']['publication_acceptance'])
  self.assertEqual(history.decode(Path(answer['history']['path']).read_bytes())['kind'],'rollback-observed')
 def test_saved_cap_wrong_cap_and_unbound_custody_hold(self):
  cap=self.live()
  for value in ({},object()):
   with self.assertRaises(self.m.Held):self.m.archive_terminal_original_vectors(self.life,self.scope,value)
  with self.assertRaises(o.Held):self.observe(cap,True)
 def test_query_last_namespace_cap_core_invalidates(self):
  cap=self.live();real=os.listdir;fired=[]
  def late(path):
   result=real(path)
   if Path(path)==cap.root and not fired:cap._contents[next(iter(cap._contents))]='0'*64;fired.append(True)
   return result
  with patch.object(self.m.os,'listdir',late),self.assertRaises(self.m.Held):self.m.archive_terminal_original_vectors(self.life,self.scope,cap)
  self.assertTrue(fired);self.assertNotIn(self.life,self.m._SEALS)
 def test_query_final_namespace_custody_path_invalidates(self):
  cap=self.live();real=os.listdir;fired=[]
  def late(path):
   result=real(path)
   if Path(path)==cap.root and not fired:self.life.input=Path('/foreign-input');fired.append(True)
   return result
  with patch.object(self.m.os,'listdir',late),self.assertRaises(self.m.Held):self.m.archive_terminal_original_vectors(self.life,self.scope,cap)
  self.assertTrue(fired)
 def test_history_last_namespace_writer_purpose_holds(self):
  cap=self.live();history.executed(cap);real=os.listdir;armed=[];fired=[];query=self.m.archive_terminal_original_vectors
  def checked(*args):
   result=query(*args);armed.append(True);return result
  def late(path):
   result=real(path)
   if len(armed)>=2 and Path(path)==cap.root and not fired:self.c.writer.local[1].allow_pending=True;fired.append(True)
   return result
  try:
   with patch.object(self.m,'archive_terminal_original_vectors',checked),patch.object(history.os,'listdir',late),self.assertRaises((o.Held,self.m.Held)):self.observe(cap)
   self.assertTrue(fired)
  finally:self.c.writer.local[1].allow_pending=False

 def provider_observe(self,reverse=False):
  sys.path.insert(0,str(Path(__file__).parent/'reader_recovery'))
  import comic_archive_repair_action as action
  cap=self.fixture(rollback=reverse)
  pp=patch.dict(sys.modules,{'mylar.publication_reader_lifecycle':self.m});pp.start();self.addCleanup(pp.stop)
  history.executed(cap)
  modules={'publication_archive_adoption':a,'publication_reader_lifecycle':self.m,'publication_archive_history':history}
  with patch.dict(sys.modules,{'mylar.publication_archive_verifier':verifier}),patch.object(sys.modules['mylar'],'publication_archive_verifier',verifier,create=True),patch.object(verifier,'installed'):
   result,vectors=action.same_child_observation(cap,modules,self.life,self.scope,self.scratch)
  action.close_vectors(vectors)
  self.assertEqual(result['summary']['operation_id'],cap.preparation._binding['operation_id']);self.assertFalse(result['summary']['ordinary_import_grant'])
  return result
 def test_actual_provider_live_forward_factory(self):
  self.assertEqual(self.provider_observe()['summary']['kind'],'fresh-repair-terminal-observation')
 def test_actual_provider_live_rollback_factory(self):
  self.assertEqual(self.provider_observe(True)['summary']['kind'],'fresh-repair-rollback-observation')

class Round(Tests):
 def setUp(self):
  super().setUp();self.output_tmp=tempfile.TemporaryDirectory();self.addCleanup(self.output_tmp.cleanup);self.round_output=Path(self.output_tmp.name);self.round_output.chmod(0o700)
 def terminal_channel_setup(self,l):
  ri,wo=os.pipe();ro,wi=os.pipe()
  for fd in (ri,wo,ro,wi):self.addCleanup(os.close,fd)
  l.channel.input=ri;l.channel.output=wi;l.channel.facts=(tuple(l.m.five(os.fstat(ri))),tuple(l.m.five(os.fstat(wi)))) if hasattr(l,'m') else (tuple(self.m.five(os.fstat(ri))),tuple(self.m.five(os.fstat(wi))))
  self.m._PIPE_SEALS[l.channel]=(ri,wi,l.channel.thread,l.channel.facts);self.parent_input=ro;self.parent_output=wo
 def refs(self):
  result={}
  for role,name in (('originals','execution-originals.json'),('execution_report','execute-report.json'),('terminal_report','terminal-report.json')):
   p=self.round_output/name;p.write_bytes(b'{}');p.chmod(0o600)
   result[role]={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'signature9':self.m.nine(p.lstat())}
  return result
 def parent(self,fault=None):
  seen=[];errors=[]
  def run():
   try:
    raw=bytearray()
    while not raw.endswith(b'\n'):
     block=os.read(self.parent_input,1)
     if not block:raise AssertionError('child channel EOF')
     raw.extend(block)
    request=self.m.decoded(raw);seen.append(request)
    reply=dict(request);reply['type']='terminal-release';reply['rights']={k:False for k in ('publication','ordinary_import','index','cleanup','replay','resume')}
    if fault=='sequence':reply['sequence']+=1
    elif fault=='rights':reply['rights']['cleanup']=True
    elif fault=='core':self.active_cap._contents[next(iter(self.active_cap._contents))]='0'*64
    elif fault=='ref':Path(request['terminal']['terminal_report']['path']).chmod(0o640)
    raw=self.m.encoded(reply)+b'\n';offset=0
    while offset<len(raw):offset+=os.write(self.parent_output,raw[offset:])
   except BaseException as error:errors.append(error)
  thread=threading.Thread(target=run);thread.start();self.addCleanup(thread.join,2)
  return seen,errors,thread
 def test_real_two_pipe_live_release_and_one_use(self):
  cap=self.live();self.active_cap=cap;refs=self.refs();seen,errors,thread=self.parent()
  witness=self.m.archive_terminal_release(self.life,self.scope,cap,refs);thread.join(2)
  self.assertFalse(thread.is_alive());self.assertFalse(errors);self.assertEqual(len(seen),1)
  value=self.m.consume_archive_terminal_release(witness,self.life,self.scope,cap);self.assertEqual(value['sequence'],seen[0]['sequence'])
  with self.assertRaises(self.m.Held):self.m.consume_archive_terminal_release(witness,self.life,self.scope,cap)
  with self.assertRaises(self.m.Held):self.m.archive_terminal_release(self.life,self.scope,cap,refs)
  with self.assertRaises(self.m.Held):self.m.consume_archive_terminal_release(json.loads(json.dumps(value)),self.life,self.scope,cap)
 def test_real_pipe_wrong_sequence_holds(self):
  cap=self.live();self.active_cap=cap;refs=self.refs();_,errors,thread=self.parent('sequence')
  with self.assertRaises(self.m.Held):self.m.archive_terminal_release(self.life,self.scope,cap,refs)
  thread.join(2);self.assertFalse(errors);self.assertNotIn(self.life,self.m._SEALS)
 def test_real_pipe_rights_drift_holds(self):
  cap=self.live();self.active_cap=cap;refs=self.refs();_,errors,thread=self.parent('rights')
  with self.assertRaises(self.m.Held):self.m.archive_terminal_release(self.life,self.scope,cap,refs)
  thread.join(2);self.assertFalse(errors)
 def test_real_pipe_late_cap_core_holds(self):
  cap=self.live();self.active_cap=cap;refs=self.refs();_,errors,thread=self.parent('core')
  with self.assertRaises(self.m.Held):self.m.archive_terminal_release(self.life,self.scope,cap,refs)
  thread.join(2);self.assertFalse(errors)
 def test_real_pipe_late_original_report_holds(self):
  cap=self.live();self.active_cap=cap;refs=self.refs();_,errors,thread=self.parent('ref')
  with self.assertRaises(self.m.Held):self.m.archive_terminal_release(self.life,self.scope,cap,refs)
  thread.join(2);self.assertFalse(errors)
 def test_consume_last_output_census_core_holds(self):
  cap=self.live();self.active_cap=cap;refs=self.refs();_,errors,thread=self.parent()
  witness=self.m.archive_terminal_release(self.life,self.scope,cap,refs);thread.join(2);self.assertFalse(errors)
  real=os.listdir;fired=[]
  def late(path):
   result=real(path)
   if Path(path)==self.round_output and not fired:cap._contents[next(iter(cap._contents))]='0'*64;fired.append(True)
   return result
  with patch.object(self.m.os,'listdir',late),self.assertRaises(self.m.Held):self.m.consume_archive_terminal_release(witness,self.life,self.scope,cap)
  self.assertTrue(fired)

 def ack_fixture(self,cap,refs):
  sys.path.insert(0,str(Path(__file__).parent/'reader_recovery'))
  import comic_archive_repair_action as action
  seen,errors,thread=self.parent();witness=self.m.archive_terminal_release(self.life,self.scope,cap,refs);thread.join(2);self.assertFalse(errors)
  value=self.m.archive_terminal_original_vectors(self.life,self.scope,cap)
  files=dict(value['terminal']['files']);files.update((r['path'],tuple(r['signature9'])) for r in refs.values())
  nodes=dict(value['terminal']['nodes']);vectors=action.seal_vectors(files,nodes,value['terminal']['absent'],dict(value['terminal']['claims']),dict(value['terminal']['namespaces']))
  return action,witness,vectors
 def test_actual_provider_ACK_inside_original_live_pipe(self):
  cap=self.live();refs=self.refs();action,witness,vectors=self.ack_fixture(cap,refs)
  class Output:
   def fileno(_):return self.life.channel.output
  from types import SimpleNamespace
  with patch.object(action.sys,'stdout',Output()):action.same_child_ack({'publication_reader_lifecycle':self.m,'publication_archive_adoption':a},self.life,self.scope,cap,witness,refs['execution_report'],vectors,{}, {},SimpleNamespace(phase='execute',source_sha256='a'*64))
  raw=os.read(self.parent_input,1024*1024);answer=json.loads(raw);self.assertEqual(answer['type'],'ACK');self.assertEqual(answer['ack']['terminal_release']['sequence'],self.life.channel.seq);self.assertFalse(answer['ack']['publication_acceptance'])
 def test_actual_provider_last_helper_core_fault_no_ACK(self):
  cap=self.live();refs=self.refs();action,witness,vectors=self.ack_fixture(cap,refs);real=action.close_vectors;fired=[]
  def late(v):real(v);cap._contents[next(iter(cap._contents))]='0'*64;fired.append(True)
  class Output:
   def fileno(_):return self.life.channel.output
  from types import SimpleNamespace
  with patch.object(action.sys,'stdout',Output()),patch.object(action,'close_vectors',late),self.assertRaises((action.Held,self.m.Held)):action.same_child_ack({'publication_reader_lifecycle':self.m,'publication_archive_adoption':a},self.life,self.scope,cap,witness,refs['execution_report'],vectors,{}, {},SimpleNamespace(phase='execute',source_sha256='a'*64))
  self.assertTrue(fired)
  import select
  self.assertFalse(select.select([self.parent_input],[],[],0)[0])

 def test_real_parent_challenges_continue_after_original_terminal_release(self):
  cap=self.live();self.active_cap=cap;refs=self.refs();seen=[];errors=[];stop=threading.Event()
  # Replace only the explicit host transport fixture with the actual owning
  # ParentPipe.challenge function, using genuine original OS pipe descriptors.
  self.life.channel.challenge=self.l.mock.temp_original.__get__(self.life.channel,self.m.ParentPipe)
  def respond():
   try:
    while not stop.is_set():
     import select
     if not select.select([self.parent_input],[],[],0.05)[0]:continue
     raw=bytearray()
     while not raw.endswith(b'\n'):raw.extend(os.read(self.parent_input,1))
     request=self.m.decoded(raw);seen.append(request)
     if request['type']=='challenge':reply={**request,**self.l.response,'type':'observation'}
     else:reply={**request,'type':'terminal-release','rights':{k:False for k in ('publication','ordinary_import','index','cleanup','replay','resume')}}
     os.write(self.parent_output,self.m.encoded(reply)+b'\n')
   except BaseException as error:errors.append(error)
  thread=threading.Thread(target=respond,daemon=True);thread.start()
  witness=self.m.archive_terminal_release(self.life,self.scope,cap,refs)
  release=self.m.consume_archive_terminal_release(witness,self.life,self.scope,cap)
  stop.set();thread.join(2);self.assertFalse(thread.is_alive());self.assertFalse(errors)
  self.assertEqual([x['sequence'] for x in seen],list(range(1,len(seen)+1)))
  terminal=next(x for x in seen if x['type']=='terminal-observation')
  self.assertEqual(release['sequence'],terminal['sequence'])
  self.assertGreater(release['conversation_sequence'],release['sequence'])
  self.assertEqual(release['conversation_sequence'],self.life.channel.seq)

 def sequence_ACK_fault(self,kind):
  cap=self.live();refs=self.refs();action,witness,vectors=self.ack_fixture(cap,refs);real=action.close_vectors;fired=[]
  def late(v):
   real(v);fired.append(True)
   if kind=='future':self.life.channel.seq+=1
   elif kind=='stale':self.life.channel.seq-=1
   elif kind=='bool':self.life.channel.seq=True
   else:self.life.channel.output=self.parent_output
  class Output:
   def fileno(_):return self.life.channel.output
  from types import SimpleNamespace
  with patch.object(action.sys,'stdout',Output()),patch.object(action,'close_vectors',late),self.assertRaises((action.Held,self.m.Held)):action.same_child_ack({'publication_reader_lifecycle':self.m,'publication_archive_adoption':a},self.life,self.scope,cap,witness,refs['execution_report'],vectors,{}, {},SimpleNamespace(phase='execute',source_sha256='a'*64))
  self.assertTrue(fired)
  import select
  self.assertFalse(select.select([self.parent_input],[],[],0)[0])
 def test_final_ACK_future_sequence_no_ACK(self):self.sequence_ACK_fault('future')
 def test_final_ACK_stale_sequence_no_ACK(self):self.sequence_ACK_fault('stale')
 def test_final_ACK_boolean_sequence_no_ACK(self):self.sequence_ACK_fault('bool')
 def test_final_ACK_foreign_pipe_no_ACK(self):self.sequence_ACK_fault('pipe')

 def final_FD_fault(self,kind,last=False):
  cap=self.fixture() if kind=='bind' else self.live();self.active_cap=cap
  refs=self.refs() if kind in ('release','consume','ACK') else None
  if kind=='consume':
   _,errors,thread=self.parent();witness=self.m.archive_terminal_release(self.life,self.scope,cap,refs);thread.join(2);self.assertFalse(errors)
  if kind=='ACK':action,witness,vectors=self.ack_fixture(cap,refs)
  fn={'bind':'bind_archive_terminal_originals','query':'archive_terminal_original_vectors','release':'archive_terminal_release','consume':'consume_archive_terminal_release','history':'observe_terminal','ACK':'same_child_ack'}[kind]
  count=[];fired=[];real=os.fstat
  def late(fd):
   result=real(fd)
   if sys._getframe(1).f_code.co_name==fn:
    count.append(fd)
    if len(count)==((4 if kind=='history' else 6) if last else (2 if kind=='history' else 4)):cap.source.chmod(0o640);fired.append(True)
   return result
  with patch.object(os,'fstat',late),self.assertRaises((o.Held,self.m.Held)):
   if kind=='bind':self.m.bind_archive_terminal_originals(self.life,self.scope,cap)
   elif kind=='query':self.m.archive_terminal_original_vectors(self.life,self.scope,cap)
   elif kind=='release':
    _,errors,thread=self.parent();self.m.archive_terminal_release(self.life,self.scope,cap,refs)
   elif kind=='consume':self.m.consume_archive_terminal_release(witness,self.life,self.scope,cap)
   elif kind=='history':self.observe(cap)
   else:
    class Output:
     def fileno(_):return self.life.channel.output
    from types import SimpleNamespace
    with patch.object(action.sys,'stdout',Output()):action.same_child_ack({'publication_reader_lifecycle':self.m,'publication_archive_adoption':a},self.life,self.scope,cap,witness,refs['execution_report'],vectors,{}, {},SimpleNamespace(phase='execute',source_sha256='a'*64))
  self.assertTrue(fired)
 def test_bind_final_pipe_FD_source_drift_holds(self):self.final_FD_fault('bind')
 def test_query_final_pipe_FD_source_drift_holds(self):self.final_FD_fault('query')
 def test_release_final_pipe_FD_source_drift_holds(self):self.final_FD_fault('release')
 def test_consume_final_pipe_FD_source_drift_holds(self):self.final_FD_fault('consume')
 def test_history_final_pipe_FD_source_drift_holds(self):self.final_FD_fault('history')
 def test_ACK_final_pipe_FD_source_drift_no_ACK(self):self.final_FD_fault('ACK')
 def test_consume_actual_last_FD_source_drift_holds(self):self.final_FD_fault('consume',last=True)
 def test_history_actual_last_FD_source_drift_holds(self):self.final_FD_fault('history',last=True)
 def test_ACK_actual_last_FD_source_drift_no_ACK(self):self.final_FD_fault('ACK',last=True)
 def test_consume_revalidation_cannot_reseal_mutated_original_witness(self):
  cap=self.live();self.active_cap=cap;refs=self.refs();_,errors,thread=self.parent();witness=self.m.archive_terminal_release(self.life,self.scope,cap,refs);thread.join(2);self.assertFalse(errors)
  real=self.m.archive_terminal_original_vectors;fired=[]
  def late(*args):
   result=real(*args);self.m._ARCHIVE_RELEASES[witness]['response_sha256']='0'*64;fired.append(True);return result
  with patch.object(self.m,'archive_terminal_original_vectors',late),self.assertRaises(self.m.Held):self.m.consume_archive_terminal_release(witness,self.life,self.scope,cap)
  self.assertTrue(fired)

if __name__=='__main__':unittest.main()
