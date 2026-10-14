"""Real Writer/SQLite, actual engine methods; only subprocess attempts projected.
No Parent constructor, registered session, NFS or installed authority is claimed.
"""
import importlib.util
from pathlib import Path
import sqlite3
import os
from types import SimpleNamespace
import subprocess
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).parent

def load(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);exec(compile(path.read_bytes(),str(path),'exec'),m.__dict__);return m
p=load(ROOT/'comic_reader_lifecycle_parent.py','owned_parent')
w=load(ROOT.parent/'media_writer.py','actual_writer')

class RemoteGuard(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.writer=w.Writer(self.root/'writer',create=True);self.engine=p.ScopedDocker()
  self.db=sqlite3.connect(self.root/'catalog.db');self.addCleanup(self.db.close);self.db.executescript('CREATE TABLE issues(IssueID TEXT PRIMARY KEY,ComicID TEXT); INSERT INTO issues VALUES("1","2");')
  self.addCleanup(lambda:p._NFS_REMOTE_WINDOWS.pop(self.engine,None))
 def calls(self):
  cid='a'*64
  return [lambda:self.engine.run(['inspect',cid],1),lambda:self.engine.canary([*p.DOCKER,'inspect',cid],capture_output=True,check=False,timeout=1),lambda:self.engine.interactive(cid,lambda *x:None,1),lambda:self.engine.worker_interactive(cid,None,1,lambda:None),lambda:self.engine.remove_observer(cid,{}),lambda:self.engine.probe_interactive(cid)]
 def test_all_remote_entrypoints_refuse_before_subprocess_under_real_writer(self):
  before=self.db.execute('SELECT * FROM issues').fetchall()
  with self.writer.hold():
   p._NFS_REMOTE_WINDOWS[self.engine]=('explicit-test-window-not-Parent-authority',)
   with patch.object(p.subprocess,'run',side_effect=AssertionError('remote-run-fired')) as run,patch.object(p.subprocess,'Popen',side_effect=AssertionError('remote-Popen-fired')) as popen:
    for call in self.calls():
     with self.assertRaisesRegex(p.Held,'nfs-no-remote-under-Writer'):call()
    run.assert_not_called();popen.assert_not_called()
   self.assertEqual(self.db.execute('SELECT * FROM issues').fetchall(),before)
 def test_uncertain_or_malformed_window_refuses(self):
  for value in (None,{},('uncertain',)):
   p._NFS_REMOTE_WINDOWS[self.engine]=value
   with self.assertRaisesRegex(p.Held,'nfs-no-remote-under-Writer'):self.engine.run(['inspect','a'*64],1)
 def test_prelease_and_physically_released_transport_keep_existing_call(self):
  result=subprocess.CompletedProcess([],0,b'[]',b'')
  with patch.object(p.subprocess,'run',return_value=result) as run:
   self.assertEqual(self.engine.run(['inspect','a'*64],1),b'[]');self.assertEqual(run.call_count,1)
   with self.writer.hold():p._NFS_REMOTE_WINDOWS[self.engine]=('test-uncertain',)
   # Fixture removes its own synthetic registry only after actual Writer exit;
   # production removal requires the genuine retained-session proof, untested here.
   p._NFS_REMOTE_WINDOWS.pop(self.engine)
   self.assertEqual(self.engine.run(['inspect','a'*64],1),b'[]');self.assertEqual(run.call_count,2)
 def epoch_fixture(self):
  # Source-method predicate projection only: actual process ticks, explicit
  # session/inspect boundary doubles; no owning Parent/Birth grant.
  owner=object.__new__(p.LifecycleParent);owner.engine=self.engine
  owner.plan={'nonce':'b'*64}
  row=dict(Id='c'*64,Name='/fixture-reader',Image='sha256:'+'d'*64,Path='fixture',Args=[],Config={},HostConfig={},Mounts=[],NetworkSettings={},State=dict(Status='running',Running=True,Paused=False,Restarting=False,OOMKilled=False,Dead=False,Pid=os.getpid(),ExitCode=0,Error='',StartedAt='fixture-original-epoch',FinishedAt=''))
  owner.baselines={'reader':row};owner.inspect=lambda cid:row
  session=SimpleNamespace(close=lambda:None,engine_replies=SimpleNamespace(sequence=0))
  p._NFS_LIVE_SESSIONS[owner]=session
  self.addCleanup(lambda:p._NFS_LIVE_SESSIONS.pop(owner,None));self.addCleanup(lambda:p._NFS_READER_EPOCHS.pop(owner,None))
  return owner,session
 def test_reader_epoch_uses_prelease_tick_only_while_actual_writer_held(self):
  owner,session=self.epoch_fixture()
  frame=dict(type='nfs-reader-epoch',nonce=owner.plan['nonce'],sequence=1,payload={})
  before=owner.nfs_reader_epoch_reply(frame)
  with self.writer.hold():
   p._NFS_REMOTE_WINDOWS[self.engine]=('test-window',)
   owner.inspect=lambda cid:(_ for _ in ()).throw(AssertionError('inspect-under-Writer'))
   frame['sequence']=2;after=owner.nfs_reader_epoch_reply(frame)
   self.assertEqual(before['payload'],after['payload'])
 def test_reader_epoch_cannot_first_capture_under_writer(self):
  owner,session=self.epoch_fixture()
  with self.writer.hold():
   p._NFS_REMOTE_WINDOWS[self.engine]=('test-window',)
   owner.inspect=lambda cid:(_ for _ in ()).throw(AssertionError('inspect-under-Writer'))
   with self.assertRaisesRegex(p.Held,'prelease-original-required'):owner.nfs_reader_epoch_reply(dict(type='nfs-reader-epoch',nonce=owner.plan['nonce'],sequence=1,payload={}))
 def test_postrelease_reader_tick_drift_is_not_adopted(self):
  owner,session=self.epoch_fixture();frame=dict(type='nfs-reader-epoch',nonce=owner.plan['nonce'],sequence=1,payload={});owner.nfs_reader_epoch_reply(frame)
  original=p._NFS_READER_EPOCHS[owner];p._NFS_READER_EPOCHS[owner]=(*original[:4],original[4]+1)
  frame['sequence']=2
  with self.assertRaisesRegex(p.Held,'postrelease-original'):owner.nfs_reader_epoch_reply(frame)

class OuterReleaseCustody(unittest.TestCase):
 def exercise(self,mutation=None,expired=False):
  # Actual outer process/FDs; Parent/module/inner-exit prerequisites projected.
  import sys,threading
  child=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.buffer.read()'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  engine=p.ScopedDocker();cid='a'*64;streams=(child.stdin,child.stdout,child.stderr)
  fds=tuple((v.fileno(),tuple(p.five(os.fstat(v.fileno())))) for v in streams)
  p.dialogue_register(engine,cid,child,streams,fds,p.time.monotonic()+10,child.pid)
  owner=object.__new__(p.LifecycleParent);owner.engine=engine;owner.thread=threading.get_ident();owner.deadline=p.time.monotonic()+5;owner.plan={'nonce':'b'*64};owner.files={};owner.nodes={};owner.generated={};owner.source_ref={};owner.plan_ref={}
  owner.core=p.encode(dict(plan=owner.plan,files=owner.files,nodes=owner.nodes,source=owner.source_ref,input=owner.plan_ref,engine=id(engine),thread=owner.thread,deadline=owner.deadline));p._CORES[owner]=owner.core
  class Lease:
   def window_state(self):return 'RELEASED_PHYSICAL'
   def physical_exit(self):
    if mutation is not None:mutation(child,streams)
    return True
  lease=Lease()
  class Probe:
   def prepared_descriptor(self):return None
  probe=Probe();probe.process=SimpleNamespace(process=child)
  session=SimpleNamespace(owner=owner,cid=cid,lease_replies=SimpleNamespace(lease=lease),probe_replies=SimpleNamespace(probe=probe));p._NFS_LIVE_SESSIONS[owner]=session
  birth=(owner,session,probe,Probe,probe.process,None,None,None,None,None,None,None,Probe.prepared_descriptor,Probe.prepared_descriptor.__code__)
  p._NFS_PROBE_BIRTHS[engine]={cid:birth}
  modules={'comic_nfs_host_lease.py':SimpleNamespace(HostWriterLease=Lease)};p._NFS_HOST_MODULES[owner]=modules;p._NFS_HOST_MODULE_SEALS[owner]=(tuple(modules.items()),())
  seal=p._DIALOGUE_SEALS[engine][cid]
  if expired:
   seal=(*seal[:6],p.time.monotonic()-1);p._DIALOGUE_SEALS[engine][cid]=seal;p._DIALOGUES[engine][cid]['deadline']=seal[6]
  launch=(birth,child,seal);p._NFS_PROBE_LAUNCHES[engine]={cid:launch}
  record=(owner,owner.core,owner.thread,owner.plan['nonce'],session,cid,lease,Lease,seal,child,Lease.window_state,Lease.window_state.__code__,Lease.physical_exit,Lease.physical_exit.__code__,birth,p.encode(dict(cid=cid)),launch);p._NFS_REMOTE_WINDOWS[engine]=record
  try:
   if mutation is None:
    owner.end_nfs_writer_window(lease);self.assertNotIn(engine,p._NFS_REMOTE_WINDOWS)
    if expired:
     with self.assertRaisesRegex(p.Held,'original-live-dialogue-drift'):p.dialogue_close(engine,cid)
   else:
    with self.assertRaises(p.Held):owner.end_nfs_writer_window(lease)
    self.assertIs(p._NFS_REMOTE_WINDOWS[engine],record)
  finally:
   child.pid=seal[3];child.stdin,child.stdout,child.stderr=streams
   streams[0].close();child.wait(timeout=3);streams[1].close();streams[2].close()
   for registry in (p._NFS_REMOTE_WINDOWS,p._NFS_PROBE_BIRTHS,p._NFS_PROBE_LAUNCHES,p._DIALOGUES,p._DIALOGUE_SEALS):registry.pop(engine,None)
   for registry in (p._CORES,p._NFS_LIVE_SESSIONS,p._NFS_HOST_MODULES,p._NFS_HOST_MODULE_SEALS):registry.pop(owner,None)
 def test_outer_dup2_during_physical_callback_retains_block(self):
  fired=[]
  def change(child,streams):
   a,b=os.pipe()
   try:os.dup2(a,streams[1].fileno());fired.append(True)
   finally:os.close(a);os.close(b)
  self.exercise(change);self.assertEqual(fired,[True])
 def test_outer_pid_mutation_retains_block(self):
  self.exercise(lambda child,streams:setattr(child,'pid',child.pid+1))
 def test_outer_stream_mutation_retains_block(self):
  self.exercise(lambda child,streams:setattr(child,'stdout',streams[2]))
 def test_expired_original_outer_release_does_not_relax_dialogue_deadline(self):
  self.exercise(expired=True)
if __name__=='__main__':unittest.main()
