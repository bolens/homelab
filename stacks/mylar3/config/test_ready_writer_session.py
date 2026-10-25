"""Connected original pipe/custody/Writer/SQLite controls; Docker profiles are disposable projections.
No live daemon, SDK installation, NFS or operational authority is asserted.
"""
import ast
import copy
import fcntl
import importlib.util
import os
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import test_publication_native_configured_scope as fixtures

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

class Connected(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.Controls('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
  for row in (self.f.native,self.f.worker,self.f.c.state):
   row['State'].update(ExitCode=0,Error='',FinishedAt='',StartedAt='original',Paused=False,Restarting=False,OOMKilled=False,Dead=False)
  self.f.c.response['reader']=copy.deepcopy(self.f.c.state)
  self.f.c.response['worker']=copy.deepcopy(self.f.worker)
  self.f.c.scope_patch.stop()
  self.api=module('publication_api',ROOT/'publication_api.py')
  self.guard=self.api.guard
  self.writers=module('media_writer',ROOT/'media_writer.py')
  self.store_module=module('workflow_store',ROOT/'workflow_store.py')
  self.store=self.store_module.Store(self.f.data)
  self.writer=self.writers.Writer(self.f.data/'media-writer',create=True)
  registry=self.guard.RegistryState(self.store.path,self.writer)
  token=registry.prepare_bootstrap(dict(manifest_sha256='a'*64,restore_sha256='b'*64,description='disposable original fixture'),epoch='c'*64)
  registry.initialize(token,accepted_token=token)
  census,_=self.guard.registry_snapshot(self.store.path,self.writer.root/'publication-v1.json')
  self.f.nvalue['publication'].update(state='ready',reason='verified',census=census)
  self.f.c.response['native']=copy.deepcopy(self.f.nvalue);self.f.write_proof();self.scope=self.f.make()
  self.controller=self.api.Controller(self.f.data,[str(self.f.library)],tool_root=Path('/opt/archiving-utils'))
  fixtures.m._OWNED_PAIRS[self.scope]=(self.controller,self.writer)
  self.parent_module=module('ready_parent',ROOT/'reader_recovery/comic_reader_lifecycle_parent.py')
  p=self.parent_module
  self.parent=object.__new__(p.LifecycleParent);x=self.parent
  x.plan=dict(version=12,nonce=self.f.c.nonce,selected_image=self.f.c.reader['child_image'],native=dict(data=str(self.f.data)))
  x.op=self.f.root;x.op_fact=tuple(p.five(self.f.root.lstat()));x.files={str(k):tuple(v) for k,v in self.scope._files.items()};x.nodes={str(k):tuple(v) for k,v in self.scope._nodes.items()};x.generated={};x.source_ref=self.f.c.parent;x.engine=object()
  x.mapping=types.SimpleNamespace(host=lambda path:path)
  self.row=dict(Id='e'*64,Image=x.plan['selected_image'],Name='/disposable-child',Path='python',Args=[],Config={},HostConfig={},Mounts=copy.deepcopy(self.f.native['Mounts']),NetworkSettings={},State=dict(Status='running',Running=True,Paused=False,Pid=os.getpid(),StartedAt='original',ExitCode=0,Error='',FinishedAt='',Restarting=False,Dead=False,OOMKilled=False))
  self.remote=[];self.remote_attempts=[];self.errors=[];self.drifts=None;self.drop_stage=None;self.response_closed=False;self.seen_ack=None;self.terminal_checks=[]
  def remote(name):
   self.remote_attempts.append(name)
   fd=os.open(self.writer.lock,os.O_RDWR|os.O_NOFOLLOW)
   try:
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise AssertionError('remote-under-Writer:'+name)
   finally:os.close(fd)
   self.remote.append(name)
  def continuous():remote('inspect-original-roles');return dict(reader=copy.deepcopy(self.f.c.state),held_native=copy.deepcopy(self.f.native),held_worker=copy.deepcopy(self.f.worker))
  def inspect(cid):remote('inspect-child');return copy.deepcopy(self.row)
  def produce(phase,context):
   remote('probe-native')
   native=copy.deepcopy(self.f.nvalue);native['publication']=self.guard.authority_status(self.store.path,self.writer.root)
   return dict(native=native,worker=copy.deepcopy(self.f.worker),child_mounts=copy.deepcopy(self.f.native['Mounts']))
  self.real_produce=produce
  x.continuous=continuous;x.inspect=inspect;x.produce=produce;x.phase_provider=lambda phase:dict(sha256=self.f.c.reader['child_source_sha256'])
  p._PROJECTORS[x]=fixtures.m.observed_native
  def terminal(input_ref,actual,message,current,original_running,raw):
   remote('independent-terminal-worker-check');self.terminal_checks.append(copy.deepcopy(message))
   return p.encode({**message,'type':'terminal-release','rights':dict(publication=False,ordinary_import=False,index=False,cleanup=False,replay=False,resume=False)})+b'\n'
  x.accept_archive_terminal=terminal
  tree=ast.parse(Path(p.__file__).read_text());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LifecycleParent');fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='child_phase');nested=next(n for n in fn.body if isinstance(n,ast.FunctionDef) and n.name=='challenge')
  # Compile the complete byte-source owning nested callback, not a mirrored predicate.
  # This fixture begins at the established-running Writer boundary. Retain its
  # exact running static/epoch; first-start diagnostics have separate owning tests.
  header=ast.parse("def factory(self,phase,input_ref,actual,cid,child_static,original_running):\n sequence=0\n writer_session=None\n writer_confirmed=False\n pending_terminal=None\n consumed_sequence=None\n started_static=encode(child_static)\n started_epoch=encode(lifecycle_state(original_running))\n started_at=original_running['State']['StartedAt']\n").body[0]
  header.body.extend([nested,ast.Return(ast.Name('challenge',ast.Load()))]);program=ast.fix_missing_locations(ast.Module([header],type_ignores=[]));ns=dict(p.__dict__);exec(compile(program,str(Path(p.__file__)),'exec'),ns)
  self.callback=ns['factory'](x,'execute',self.f.c.input,[],self.row['Id'],p.static(self.row),copy.deepcopy(self.row))
  ri,wo=os.pipe();ro,wi=os.pipe();self.requests=ri;self.response_out=wi
  self.f.c.channel.input=ro;self.f.c.channel.output=wo;self.f.c.channel.facts=(tuple(fixtures.l.five(os.fstat(ro))),tuple(fixtures.l.five(os.fstat(wo))))
  fixtures.l._PIPE_SEALS[self.f.c.channel]=(ro,wo,self.f.c.channel.thread,self.f.c.channel.facts,self.f.c.channel.deadline)
  # Custody was formed against the original pipe; the new fixture must be born
  # against these actual two pipes, not rebaseline an admitted custody object.
  self.f.custody=self.f.c.make();self.scope=self.f.make();fixtures.m._OWNED_PAIRS[self.scope]=(self.controller,self.writer)
  self.addCleanup(os.close,ro);self.addCleanup(os.close,wo);self.addCleanup(os.close,ri);self.addCleanup(lambda:None if self.response_closed else os.close(wi))
  own=types.SimpleNamespace(sdk=lambda:[self.api,self.writers,self.guard])
  real_import=fixtures.m.importlib.import_module
  def imports(name,*args,**kwargs):
   if name=='mylar.publication_native_configured_scope':return fixtures.m
   if name=='mylar.publication_archive_owned':return own
   return real_import(name,*args,**kwargs)
  self.import_patch=patch.object(fixtures.m.importlib,'import_module',imports);self.import_patch.start();self.addCleanup(self.import_patch.stop)
  self.f.c.mock.stop()
  self.running=True
  def server():
   pending=b''
   try:
    while self.running:
     block=os.read(ri,65536)
     if not block:break
     pending+=block
     while b'\n' in pending:
      raw,_,pending=pending.partition(b'\n');message=p.decode(raw)
      if message.get('type')=='ACK':self.seen_ack=message['ack'];continue
      if self.drifts:self.drifts(message)
      response=self.callback(message,raw)
      if self.drop_stage is not None and message.get('writer_session',{}).get('stage')==self.drop_stage:
       self.response_closed=True;os.close(wi);return
      os.write(wi,response)
   except BaseException as e:
    self.errors.append(e)
    if not self.response_closed:self.response_closed=True;os.close(wi)
  self.thread=threading.Thread(target=server,daemon=True);self.thread.start()
 def tearDown(self):
  self.running=False
 def test_connected_original_census_held_idle_no_remote_then_ready(self):
  with self.scope.writer_session(self.controller,self.writer):
   before=len(self.remote);self.scope.revalidate();self.callback(None)
   self.assertEqual(len(self.remote),before)
   fd=os.open(self.writer.lock,os.O_RDWR|os.O_NOFOLLOW)
   try:
    with self.assertRaises(BlockingIOError):fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
   finally:os.close(fd)
   self.assertEqual(self.scope.binding['census'],self.f.nvalue['publication']['census'])
  self.assertEqual(self.guard.authority_status(self.store.path,self.writer.root)['state'],'ready');self.assertFalse(self.errors)
 def test_actual_refused_acquisition_leaves_without_work(self):
  from contextlib import contextmanager
  @contextmanager
  def refused(**kwargs):raise self.writers.Busy('fixture-held');yield
  with patch.object(self.writer,'hold',refused),self.assertRaises(self.writers.Busy):
   with self.scope.writer_session(self.controller,self.writer):self.fail('work after refusal')
  self.assertNotIn(self.f.custody,fixtures.l._WRITER_PIPE);self.assertFalse(self.errors)
 def test_actual_own_writer_census_epoch_drift_refuses(self):
  with self.assertRaises((fixtures.m.Held,fixtures.l.Held)):
   with self.scope.writer_session(self.controller,self.writer):
    original=self.guard.registry_snapshot
    def drift(*args):
     census,records=original(*args);census['epoch']='f'*64;return census,records
    with patch.object(self.guard,'registry_snapshot',drift):self.scope.revalidate()
 def test_redirect_same_census_database_after_enter_is_refused(self):
  import shutil
  other=self.f.root/'foreign-workflow.sqlite';shutil.copyfile(self.controller.database,other);other.chmod(0o600)
  import sqlite3
  from contextlib import closing
  with closing(sqlite3.connect(other)) as db:self.assertEqual(self.guard.complete_census(db)[0],self.f.nvalue['publication']['census'])
  with self.assertRaises(self.guard.Unavailable):self.guard.registry_snapshot(other,self.writer.root/'publication-v1.json')
  with self.assertRaises(fixtures.m.Held):
   with self.scope.writer_session(self.controller,self.writer):
    self.controller.database=other;self.scope._writer_proof()
 def test_registry_callback_tool_and_native_paths_are_refused(self):
  original=self.guard.registry_snapshot;fired=[]
  def redirect(*args):
   answer=original(*args);fired.append(True)
   self.controller.tool_root=Path('/foreign-tools');self.controller.native_database=self.f.root/'foreign-mylar.db'
   return answer
  with self.assertRaises(fixtures.m.Held):
   with self.scope.writer_session(self.controller,self.writer):
    with patch.object(self.guard,'registry_snapshot',redirect):self.scope._writer_proof()
  self.assertTrue(fired)
 def test_preentry_derived_database_and_tool_root_must_be_configured(self):
  import shutil
  other=self.f.root/'foreign-workflow.sqlite';shutil.copyfile(self.controller.database,other);other.chmod(0o600)
  self.controller.database=other;self.controller.tool_root=Path('/foreign-tools')
  with self.assertRaises(fixtures.m.Held):
   with self.scope.writer_session(self.controller,self.writer):self.fail('foreign pair entered')

 def test_existing_pipe_original_nonce_is_not_optional(self):
  with self.assertRaises(fixtures.l.Held):
   self.f.c.channel.challenge('f'*64,self.f.c.input['sha256'],self.f.c.parent['sha256'])

 def test_enter_failure_never_acquires_writer(self):
  def wrong(message):
   if message.get('writer_session',{}).get('stage')=='enter':message['nonce']='f'*64
  self.drifts=wrong
  with self.assertRaises(fixtures.l.Held):
   with self.scope.writer_session(self.controller,self.writer):self.fail('work after refused enter')
  self.assertEqual(getattr(self.writer.local[1],'depth',0),0)
 def test_lost_enter_response_has_no_work_or_replay(self):
  self.drop_stage='enter'
  with self.assertRaises(fixtures.l.Held):
   with self.scope.writer_session(self.controller,self.writer):self.fail('work after lost enter')
  self.assertEqual(getattr(self.writer.local[1],'depth',0),0)
 def test_lost_leave_response_retains_uncertain_custody(self):
  self.drop_stage='leave'
  with self.assertRaises(fixtures.l.Held):
   with self.scope.writer_session(self.controller,self.writer):self.scope.revalidate()
  self.assertEqual(getattr(self.writer.local[1],'depth',0),0)
  self.assertIn(self.f.custody,fixtures.l._WRITER_PIPE)
 def test_changed_original_binding_is_refused_under_real_lease(self):
  def changed(message):
   if message.get('writer_session',{}).get('stage')=='held':message['writer_session']['census']['epoch']='f'*64
  self.drifts=changed
  with self.assertRaises(fixtures.l.Held):
   with self.scope.writer_session(self.controller,self.writer):self.scope.revalidate()
 def test_pending_terminal_ACK_precedes_leave_and_independent_check(self):
  l=fixtures.l;channel=self.f.c.channel
  with self.scope.writer_session(self.controller,self.writer):
   self.scope.revalidate();before=len(self.remote)
   channel.seq+=1
   message=dict(protocol='reader-lifecycle-pipe-v1',type='terminal-observation',nonce=self.f.c.nonce,
                input_sha256=self.f.c.input['sha256'],parent_sha256=self.f.c.parent['sha256'],sequence=channel.seq,
                challenge='d'*64,terminal={'fixture':'pending only; no configured grant'})
   os.write(channel.output,l.encoded(message)+b'\n');raw=b''
   while not raw.endswith(b'\n'):raw+=os.read(channel.input,1)
   response=l.decoded(raw);self.assertEqual(response['type'],'terminal-release');self.assertTrue(all(v is False for v in response['rights'].values()))
   self.assertEqual(len(self.remote),before);self.assertEqual(self.terminal_checks,[])
   self.scope.revalidate();self.assertEqual(len(self.remote),before)
   consumed=channel.seq
   os.write(channel.output,l.encoded(dict(type='ACK',ack=dict(terminal_sequence=message['sequence'],conversation_sequence=consumed)))+b'\n')
   self.assertGreater(self.writer.local[1].depth,0)
  self.assertEqual(len(self.terminal_checks),1);self.assertIsNotNone(self.seen_ack)
  state={name:cell.cell_contents for name,cell in zip(self.callback.__code__.co_freevars,self.callback.__closure__)}
  self.assertEqual(state['consumed_sequence'],self.seen_ack['conversation_sequence'])
  self.assertEqual(state['sequence'],state['consumed_sequence']+1);self.assertIsNone(state['writer_session'])
 def test_legacy_unannounced_writer_connected_RPC_is_refused(self):
  before=len(self.remote_attempts)
  with self.writer.hold(timeout=0),self.assertRaises(fixtures.l.Held):self.scope.revalidate()
  self.assertGreater(len(self.remote_attempts),before)
  self.assertTrue(any(isinstance(e,AssertionError) and 'remote-under-Writer' in str(e) for e in self.errors))
 def test_postrelease_original_config_drift_never_accepts_leave(self):
  armed=[]
  def arm(message):
   if message.get('writer_session',{}).get('stage')=='leave':armed.append(True)
  self.drifts=arm
  def changed(*args):
   result=self.real_produce(*args)
   if armed:self.f.config.chmod(0o640)
   return result
  self.parent.produce=changed
  with self.assertRaises(fixtures.l.Held):
   with self.scope.writer_session(self.controller,self.writer):self.scope.revalidate()
  self.assertTrue(armed);self.assertIn(self.f.custody,fixtures.l._WRITER_PIPE)
 def test_actual_interactive_postACK_gate_accepts_only_single_leave_kind(self):
  tree=ast.parse(Path(self.parent_module.__file__).read_text())
  function=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='interactive')
  check=next(n for n in ast.walk(function) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='need' and len(n.args)==2 and isinstance(n.args[1],ast.Constant) and n.args[1].value=='child-dialogue-after-final-ACK')
  expr=compile(ast.fix_missing_locations(ast.Expression(check.args[0])),'owning-after-ACK-gate','eval')
  for stage in ('enter','held','leave'):
   value=dict(type='challenge',writer_session=dict(stage=stage))
   self.assertEqual(eval(expr,{},dict(ack={'original':True},message=value)),stage=='leave')
  self.assertFalse(eval(expr,{},dict(ack={'original':True},message={'type':'terminal-observation'})))
if __name__=='__main__':unittest.main()
