"""Actual nested Popen/OS pipes and SQLite; Docker/profile/birth are labelled fixtures.

No container/runtime/image/mount or protected-cap acceptance is claimed here.
"""
import copy
from contextlib import closing
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_archive_same_child_parent as prior
from test_reader_lifecycle_parent import fixture_ref
p=prior.p
HERE=Path(__file__).resolve().parent
WORKER=HERE/'_archive_worker_fixtures/archive_terminal_observation.py'

class Tests(unittest.TestCase):
 setUp=prior.Tests.setUp
 setup=prior.Tests.setup
 go=prior.Tests.go
 def unit5(self):
  worker_entry=getattr(self,'worker_entry',WORKER)
  self.setup();x=self.parent;x.plan.update(version=12,native={'data':str(self.root),'roots':[str(self.root)]})
  self.archive=self.root/'Comic.cbz';self.archive.write_bytes(b'preserved fixture archive bytes')
  self.catalog=self.root/'mylar.db';self.authority=self.root/'workflow.sqlite';writer=self.root/'media-writer';writer.mkdir(mode=0o700);self.marker=writer/'publication-v1.json';self.marker.write_bytes(b'{}')
  with closing(sqlite3.connect(self.catalog)) as db,db:
   db.execute('CREATE TABLE comics(ComicID TEXT,ComicLocation TEXT)');db.execute('CREATE TABLE issues(IssueID TEXT,ComicID TEXT,Location TEXT,Status TEXT)');db.execute('CREATE TABLE annuals(IssueID TEXT,ComicID TEXT,ReleaseComicID TEXT,Location TEXT,Status TEXT,Deleted INT)')
   db.execute('INSERT INTO comics VALUES(?,?)',('456',str(self.root)));db.execute('INSERT INTO issues VALUES(?,?,?,?)',('123','456','Comic.cbz','Downloaded'))
  with closing(sqlite3.connect(self.authority)) as db,db:db.execute('CREATE TABLE records(k TEXT,v TEXT)')
  spec=importlib.util.spec_from_file_location('unit5_actual_pure_vectors',HERE/'comic_archive_worker_vectors.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  # Source-owned host fixture selectors; neither __file__ nor SDK types change.
  module.READ_ROOTS=(str(self.root),);module.SOURCE_ENTRY=str(worker_entry)
  p._WORKER_MODULES[x]=module
  p._WORKER_FUNCTIONS[x]=(tuple((n,module.__dict__[n],module.__dict__[n].__code__) for n in ('need','encode','decode','digest','path','put','frame','pack','mapping','freeze','response')),module.Round,tuple(module.Round.__dict__.items()),module.Round.__init__.__code__,module.Round.accept.__code__)
  sha=hashlib.sha256(worker_entry.read_bytes()).hexdigest();x.plan['worker_observation']={'mode':'original-pipes-v1','source':{'path':str(worker_entry),'sha256':sha,'signature9':p.nine(worker_entry.lstat())},'image_sources':{}}
  x.baselines={'held_worker':{'Image':'sha256:'+'7'*64}};x.baselines['held_worker']['Mounts']=[dict(Type='bind',Source=str(self.root),Destination=str(self.root),RW=True)]
  rolepaths={'archive':self.archive,'catalog':self.catalog,'authority':self.authority,'marker':self.marker};roles={k:dict(path=str(v),signature9=p.nine(v.lstat()),sha256=hashlib.sha256(v.read_bytes()).hexdigest()) for k,v in rolepaths.items()};roles['catalog_native_target']=str(self.archive)
  terminal=p.decode(Path(self.terminal['path']).read_bytes());terminal['worker_roles']=roles;terminal['independent_observation']['source_sha256']=roles['archive']['sha256']
  terminal['original_vectors']['files'] += [[str(v),p.nine(v.lstat())] for v in rolepaths.values()]
  nodes={str(n):p.five(n.lstat()) for v in rolepaths.values() for n in v.parents};terminal['original_vectors']['nodes'] += list(nodes.items())
  terminal['original_vectors']['absent'] += [str(v)+s for v in (self.catalog,self.authority) for s in ('-journal','-wal','-shm')]
  self.terminal=fixture_ref(Path(self.terminal['path']),p.encode(terminal));self.refs['terminal_report']=self.terminal;self.message['terminal']['terminal_report']=self.terminal
  er=Path(self.refs['execution_report']['path']);execute=p.decode(er.read_bytes());execute['terminal_report']=self.terminal;self.refs['execution_report']=fixture_ref(er,p.encode(execute));self.message['terminal']['execution_report']=self.refs['execution_report']
  self.producer_row=copy.deepcopy(self.current);self.worker_row=None;self.worker_process=None;self.engine=p.ScopedDocker();x.engine=self.engine
  self.image_labels={'org.opencontainers.image.source':'https://github.com/bolens/homelab','org.opencontainers.image.title':'Comic normalization and import recovery'}
  image_ref=fixture_ref(self.root/'worker-image.json',p.encode([dict(Id=x.baselines['held_worker']['Image'],Config={'Labels':self.image_labels})]))
  image_patch=patch.object(p,'WORKER_OBSERVATION_IMAGE_ORIGINAL',image_ref);image_patch.start();self.addCleanup(image_patch.stop)
  self.processes=[];self.both=[];self.fault=None;self.worker_final=False
  real=subprocess.Popen
  producer_script="import sys,json;message=json.loads(sys.argv[1]);print(json.dumps(message,sort_keys=True,separators=(',',':')),flush=True);reply=sys.stdin.buffer.readline();assert json.loads(reply)['type']=='terminal-release';print(json.dumps({'type':'ACK','ack':{'fixture':'synthetic-parent-facts-only'}},sort_keys=True,separators=(',',':')),flush=True)"
  worker_script="import importlib.util,sys;path=sys.argv[1];root=sys.argv[2];args=sys.argv[3:];s=importlib.util.spec_from_file_location('actual_worker_entry',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.READ_ROOTS=(root,);sys.argv=[path,*args];m.main()"
  def spawn(args,**kw):
   cid=args[-1]
   if cid=='4'*64:
    proc=real([sys.executable,'-I','-B','-c',producer_script,p.encode(self.message).decode()],**kw);self.producer_row['State']['Pid']=proc.pid
   else:
    intent=p._WORKER_INTENTS[x];cmd=list(intent[1]);proc=real([sys.executable,'-I','-B','-c',worker_script,str(worker_entry),str(self.root),*cmd[3:]],**kw);self.worker_process=proc
   self.processes.append(proc);return proc
  def run(args,seconds):
   self.assertEqual(args[0],'create');self.worker_row=self.worker_profile('created');return ('5'*64).encode()
  def inspect(cid):
   if cid=='4'*64:return copy.deepcopy(self.producer_row)
   state='created' if self.worker_process is None else 'exited' if self.worker_process.poll() is not None else 'running'
   row=self.worker_profile(state)
   if self.fault:self.fault(state)
   return row
  def remove(cid,row):
   self.assertEqual(cid,'5'*64);self.assertEqual(row['State']['ExitCode'],0);self.worker_final=True
  def continuous():
   if self.worker_process is not None and '5'*64 in p._DIALOGUES.get(self.engine,{}):
    self.assertEqual(set(p._DIALOGUES[self.engine]),{'4'*64,'5'*64});self.both.append(True)
   return {}
  x.inspect=inspect;x.continuous=continuous
  # Explicit initial parent-admission fixture BEFORE the actual pipe dialogue.
  x.core=p.encode(dict(plan=x.plan,files=x.files,nodes=x.nodes,source=x.source_ref,input=x.plan_ref,engine=id(x.engine),thread=x.thread,deadline=x.deadline));p._CORES[x]=x.core
  self.addCleanup(lambda:[proc.kill() for proc in self.processes if proc.poll() is None])
  self.addCleanup(lambda:[proc.wait(timeout=2) for proc in self.processes])
  self.patches=[patch.object(p,'WORKER_OBSERVATION_ENABLED',True),patch.object(p.subprocess,'Popen',spawn),patch.object(self.engine,'run',run),patch.object(self.engine,'remove_observer',remove)]
  for v in self.patches:v.start();self.addCleanup(v.stop)
 def worker_profile(self,state):
  intent=p._WORKER_INTENTS[self.parent];args,cmd,mounts,name,ref,roots,image,_deadline=intent
  host=dict(ReadonlyRootfs=True,Privileged=False,NetworkMode='none',IpcMode='private',PidMode='',CapDrop=['ALL'],CapAdd=[],SecurityOpt=['no-new-privileges'],PidsLimit=32,Memory=768*1024**2,MemorySwap=768*1024**2,NanoCpus=500000000,RestartPolicy={'Name':'no'},Devices=[],DeviceRequests=[],Binds=[],Tmpfs={},PortBindings={})
  status=dict(Status=state,Running=state=='running',Pid=self.worker_process.pid if state=='running' else 0,StartedAt='original-worker-start' if state!='created' else '',FinishedAt='end' if state=='exited' else '',ExitCode=0,Error='',Paused=False,Restarting=False,Dead=False,OOMKilled=False)
  return dict(Id='5'*64,Image=image,Name=name,Path='python3',Args=list(cmd),Config=dict(User='1000:1000',Entrypoint=['python3'],Cmd=list(cmd),OpenStdin=True,Tty=False,Labels=dict(self.image_labels,**{'com.homelab.reader.worker-observer':name})),HostConfig=host,Mounts=[dict(Type='bind',Source=a,Destination=b,RW=False) for a,b in mounts],NetworkSettings={},State=status)
 def run_nested(self):
  def handler(value,raw=None):
   if value is None:return None
   return self.parent.accept_archive_terminal(self.proof,[],value,copy.deepcopy(self.producer_row),copy.deepcopy(self.producer_row),raw)
  return self.engine.interactive('4'*64,handler,10)
 def test_worker_intent_budget_is_fixed_once_at_creation(self):
  self.unit5();x=self.parent;x.deadline=300;cid='4'*64
  x.emit=lambda *args:copy.deepcopy(self.action)
  p._DIALOGUE_SEALS.setdefault(self.engine,{})[cid]=(None,)*6+(250,)
  with patch.object(p,'dialogue_close',return_value=object()),patch.object(p.time,'monotonic',return_value=100):
   x.worker_intent(self.current)
  intent=p._WORKER_INTENTS[x];self.assertEqual(intent[7],190)
  with patch.object(p.time,'monotonic',return_value=210),self.assertRaises(p.Held):x.worker_intent(self.current)
  self.assertIs(p._WORKER_INTENTS[x],intent);self.assertEqual(intent[7],190)
 def test_worker_intent_keeps_both_earlier_enclosing_deadlines(self):
  self.unit5();cid='4'*64
  for parent_end,producer_end,expected in ((125,180,125),(180,125,125)):
   x=copy.copy(self.parent);x.deadline=parent_end;x.emit=lambda *args:copy.deepcopy(self.action)
   p._WORKER_MODULES[x]=p._WORKER_MODULES[self.parent]
   self.addCleanup(p._WORKER_MODULES.pop,x,None);self.addCleanup(p._WORKER_INTENTS.pop,x,None)
   p._DIALOGUE_SEALS.setdefault(self.engine,{})[cid]=(None,)*6+(producer_end,)
   with patch.object(p,'dialogue_close',return_value=object()),patch.object(p.time,'monotonic',return_value=100):x.worker_intent(self.current)
   self.assertEqual(p._WORKER_INTENTS[x][7],expected)
 def test_genuine_nested_original_pipes_worker_readback_before_producer_release(self):
  self.unit5();ack=self.run_nested();self.assertEqual(ack,{'fixture':'synthetic-parent-facts-only'});self.assertTrue(self.both);self.assertTrue(self.worker_final)
  result=p._ARCHIVE_TERMINAL_ROUNDS[self.parent]['worker_result'];self.assertEqual(result['type'],'observed');self.assertTrue(all(v is False for v in result['rights'].values()))
 def test_current_parent_and_current_worker_complete_actual_pipes(self):
  self.worker_entry=HERE/'_current_worker_source/archive_terminal_observation.py'
  self.unit5();self.assertEqual(self.run_nested(),{'fixture':'synthetic-parent-facts-only'})
  self.assertTrue(self.worker_final);self.assertTrue(self.both)
 def wide_worker_exchange(self):
  self.unit5()
  terminal=p.decode(Path(self.terminal['path']).read_bytes())
  directory=self.root/('representative-private-control-parent-'+'x'*120);directory.mkdir()
  terminal['original_vectors']['nodes'].append([str(directory),p.five(directory.lstat())])
  for index in range(77):
   path=directory/('control-'+str(index)+'-'+'x'*60);path.write_bytes(b'original fixture')
   terminal['original_vectors']['files'].append([str(path),p.nine(path.lstat())])
  self.terminal=fixture_ref(Path(self.terminal['path']),p.encode(terminal));self.refs['terminal_report']=self.terminal;self.message['terminal']['terminal_report']=self.terminal
  er=Path(self.refs['execution_report']['path']);execute=p.decode(er.read_bytes());execute['terminal_report']=self.terminal
  self.refs['execution_report']=fixture_ref(er,p.encode(execute));self.message['terminal']['execution_report']=self.refs['execution_report']
 def test_wide_actual_round_has_fixed_full_closure_boundaries(self):
  self.wide_worker_exchange();flags=[];boundaries=[];original=self.engine.worker_interactive
  def transport(cid,protocol,seconds,guard,**options):
   def checked(**kwargs):
    result=guard(**kwargs);boundaries.append(kwargs['boundary'])
    fd=p._DIALOGUES[self.engine][cid]['descriptors'][0][0]
    flags.append(p.fcntl.fcntl(fd,p.fcntl.F_GETFL));return result
   return original(cid,protocol,seconds,checked,**options)
  with patch.object(self.engine,'worker_interactive',side_effect=transport):
   self.assertEqual(self.run_nested(),{'fixture':'synthetic-parent-facts-only'})
  self.assertEqual(boundaries,['incoming','parsed','commit']*3+['incoming','parsed','complete'])
  self.assertTrue(self.worker_final);self.assertTrue(all(value&os.O_NONBLOCK for value in flags))
 def test_small_round_has_same_full_closure_boundaries(self):
  self.unit5();boundaries=[];original=self.engine.worker_interactive
  def transport(cid,protocol,seconds,guard,**options):
   def checked(**kwargs):
    result=guard(**kwargs);boundaries.append(kwargs['boundary']);return result
   return original(cid,protocol,seconds,checked,**options)
  with patch.object(self.engine,'worker_interactive',side_effect=transport):self.run_nested()
  self.assertEqual(boundaries,['incoming','parsed','commit']*3+['incoming','parsed','complete'])
 def test_commit_tail_refuses_hostile_pid_without_equality(self):
  self.unit5();called=[];original=self.engine.worker_interactive
  class Foreign:
   def __eq__(self,other):called.append(True);return True
   def __ne__(self,other):called.append(True);return False
  def transport(cid,protocol,seconds,guard,**options):
   saved=[]
   def checked(**kwargs):
    result=guard(**kwargs)
    if protocol.step==1 and kwargs.get('boundary')=='commit':
     saved.append(self.worker_process.pid);self.worker_process.pid=Foreign()
    return result
   try:return original(cid,protocol,seconds,checked,**options)
   finally:
    if saved:self.worker_process.pid=saved[0]
  with patch.object(self.engine,'worker_interactive',side_effect=transport),self.assertRaises(p.Held):self.run_nested()
  self.assertFalse(called);self.assertFalse(self.worker_final)
 def test_payload_preserves_suffix_after_short_write_and_eagain(self):
  raw=b'x'*150000;sent=bytearray();attempts=[];checks=[]
  def write(fd,data):
   attempts.append(len(data))
   if len(attempts)==1:raise BlockingIOError(11,'synthetic readiness race')
   count=min(len(data),997);sent.extend(data[:count]);return count
  p._worker_payload(4,raw,10,lambda:checks.append(True),write,lambda r,w,e,t:([],w,[]),lambda:0)
  self.assertEqual(bytes(sent),raw);self.assertNotIn(10,sent)
  self.assertLessEqual(max(attempts),65536);self.assertGreater(len(attempts),100)
  self.assertEqual(len(checks),2*len(attempts))
 def test_payload_rejects_delimiter_no_progress_and_expired_wait(self):
  for raw,count,clock in ((b'x\ny',1,0),(b'abc',0,0),(b'abc',1,10)):
   with self.subTest(raw=raw,count=count,clock=clock),self.assertRaises(p.Held):
    p._worker_payload(4,raw,10,lambda:None,lambda fd,data:count,lambda r,w,e,t:([],w,[]),lambda:clock)
 def test_worker_guard_cannot_restore_blocking_pipe_before_write(self):
  self.unit5();original=self.engine.worker_interactive;changed=[]
  def transport(cid,protocol,seconds,guard,**transport_options):
   def checked(**kwargs):
    result=guard(**kwargs)
    if protocol.step==1 and kwargs.get('boundary')=='commit' and not changed:
     fd=p._DIALOGUES[self.engine][cid]['descriptors'][0][0]
     p.fcntl.fcntl(fd,p.fcntl.F_SETFL,p.fcntl.fcntl(fd,p.fcntl.F_GETFL)&~os.O_NONBLOCK);changed.append(fd)
    return result
   return original(cid,protocol,seconds,checked,**transport_options)
  with patch.object(self.engine,'worker_interactive',side_effect=transport),self.assertRaises(p.Held):self.run_nested()
  self.assertTrue(changed);self.assertFalse(self.worker_final)
 def test_worker_pipe_kernel_substitution_is_refused_before_write(self):
  self.unit5();original=self.engine.worker_interactive;primitive=p.fcntl.fcntl;changed=[];called=[]
  def foreign(*args):called.append(True);raise AssertionError('foreign pipe kernel')
  def transport(cid,protocol,seconds,guard,**transport_options):
   def checked(**kwargs):
    result=guard(**kwargs)
    if protocol.step==1 and not changed:p.fcntl.fcntl=foreign;changed.append(True)
    return result
   return original(cid,protocol,seconds,checked,**transport_options)
  try:
   with patch.object(self.engine,'worker_interactive',side_effect=transport),self.assertRaises(p.Held):self.run_nested()
  finally:p.fcntl.fcntl=primitive
  self.assertTrue(changed);self.assertFalse(called);self.assertFalse(self.worker_final)
 def test_payload_metadata_change_is_refused_before_delimiter_commit(self):
  self.wide_worker_exchange();changed=[];original=self.engine.worker_interactive
  def transport(cid,protocol,seconds,guard,**options):
   def checked(**kwargs):
    if protocol.step==1 and kwargs.get('boundary')=='commit' and not changed:
     self.marker.chmod(0o640);changed.append(True)
    return guard(**kwargs)
   return original(cid,protocol,seconds,checked,**options)
  with patch.object(self.engine,'worker_interactive',side_effect=transport),self.assertRaises(p.Held):self.run_nested()
  self.assertTrue(changed);self.assertFalse(self.worker_final)
 def test_pipe_setup_failure_attempts_every_stream_close(self):
  self.unit5();spawn=p.subprocess.Popen;primitive=p.fcntl.fcntl;closed=[]
  class Closing:
   def __init__(self,stream,index):self.stream=stream;self.index=index
   def fileno(self):return self.stream.fileno()
   def close(self):
    closed.append(self.index);self.stream.close()
    if self.index==0:raise OSError('synthetic close failure')
  def foreign(*args):raise AssertionError('foreign pipe kernel invoked')
  def start(args,**kwargs):
   process=spawn(args,**kwargs)
   if args[-1]=='5'*64:
    process.stdin=Closing(process.stdin,0);process.stdout=Closing(process.stdout,1);process.stderr=Closing(process.stderr,2)
    p.fcntl.fcntl=foreign
   return process
  try:
   with patch.object(p.subprocess,'Popen',side_effect=start),self.assertRaises(p.Held):self.run_nested()
  finally:p.fcntl.fcntl=primitive
  self.assertEqual(closed[:3],[0,1,2]);self.assertFalse(self.worker_final)
 def final_frame_after_process_exit(self,corrupt=None):
  if corrupt in ('foreign','missing'):
   temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
   self.worker_entry=Path(temp.name)/'archive_terminal_observation.py'
   source=WORKER.read_text();old="final = encode(dict(release, type='released'))"
   new="final = encode(dict(release, type='foreign'))" if corrupt=='foreign' else "return None  # Synthetic missing final reply."
   self.assertEqual(source.count(old),1);self.worker_entry.write_text(source.replace(old,new))
  self.unit5();released=[];changed=[];original=self.engine.worker_interactive;real_stat=p.nfs_lstat
  def sample(path):
   value=real_stat(path)
   if corrupt=='metadata-expired' and released and str(path)==self.source['path'] and not changed:
    changed.append(True);end=p._DIALOGUES[self.engine]['5'*64]['deadline']
    while time.monotonic()<end:time.sleep(max(0,min(.01,end-time.monotonic())))
   return value
  def transport(cid,protocol,seconds,guard,**options):
   if corrupt in ('expired','metadata-expired'):options['_deadline']=min(options['_deadline'],time.monotonic()+1)
   def checked(**kwargs):
    if protocol.step==3 and kwargs.get('boundary')=='incoming' and not released:
     self.worker_process.wait(timeout=3);released.append(True)
     if corrupt=='expired':
      end=p._DIALOGUES[self.engine][cid]['deadline']
      while time.monotonic()<end:time.sleep(max(0,min(.01,end-time.monotonic())))
    return guard(**kwargs)
   return original(cid,protocol,seconds,checked,**options)
  with patch.object(p,'nfs_lstat',side_effect=sample),patch.object(self.engine,'worker_interactive',side_effect=transport):
   if corrupt:
    with self.assertRaises(p.Held):self.run_nested()
    self.assertFalse(self.worker_final)
   else:
    self.assertEqual(self.run_nested(),{'fixture':'synthetic-parent-facts-only'});self.assertTrue(self.worker_final)
  if corrupt!='missing':self.assertTrue(released)
  if corrupt=='metadata-expired':self.assertTrue(changed)
 def test_worker_final_buffered_frame_accepts_original_natural_exit(self):
  self.final_frame_after_process_exit()
 def test_worker_exited_with_foreign_final_frame_refuses(self):
  self.final_frame_after_process_exit('foreign')
 def test_worker_exited_without_final_frame_refuses(self):
  self.final_frame_after_process_exit('missing')

 def test_worker_original_deadline_still_checked_with_final_frame_pending(self):
  self.final_frame_after_process_exit('expired')

 def test_worker_metadata_cannot_dispatch_read_after_original_deadline(self):
  self.final_frame_after_process_exit('metadata-expired')
 def test_worker_last_write_guard_cannot_replace_original_response_fd(self):
  self.unit5();r,w=os.pipe();saved=[];counts=[];original=self.engine.worker_interactive
  def interactive(cid,protocol,seconds,guard,**transport_options):
   def changed(**kwargs):
    result=guard(**kwargs)
    if protocol.step==1 and kwargs.get('boundary')=='commit':
     counts.append(True)
     if len(counts)==1:
      fd=p._DIALOGUES[self.engine][cid]['descriptors'][0][0];saved.append(os.dup(fd));os.dup2(w,fd)
    return result
   return original(cid,protocol,seconds,changed,**transport_options)
  try:
   with patch.object(self.engine,'worker_interactive',side_effect=interactive),self.assertRaises(p.Held):self.run_nested()
   self.assertTrue(saved);os.set_blocking(r,False)
   with self.assertRaises(BlockingIOError):os.read(r,1)
   self.assertFalse(self.worker_final)
  finally:
   for fd in saved:os.close(fd)
   os.close(r);os.close(w)

 def test_worker_final_kernel_substitution_never_runs_foreign_callback(self):
  self.unit5();original=self.engine.worker_interactive;fstat=p.os.fstat;called=[];counts=[]
  def foreign(fd):called.append(True);raise AssertionError('foreign final fstat')
  def interactive(cid,protocol,seconds,guard,**transport_options):
   def changed(**kwargs):
    result=guard(**kwargs)
    if protocol.step==1 and kwargs.get('boundary')=='commit':
     counts.append(True)
     if len(counts)==1:p.os.fstat=foreign
    return result
   return original(cid,protocol,seconds,changed,**transport_options)
  try:
   with patch.object(self.engine,'worker_interactive',side_effect=interactive),self.assertRaises(p.Held):self.run_nested()
  finally:p.os.fstat=fstat
  self.assertEqual(len(counts),1);self.assertFalse(called);self.assertFalse(self.worker_final)

 def test_worker_last_write_guard_cannot_mutate_original_dialogue_record(self):
  self.unit5();original=self.engine.worker_interactive;counts=[];changed=[]
  def interactive(cid,protocol,seconds,guard,**transport_options):
   def callback(**kwargs):
    result=guard(**kwargs)
    if protocol.step==1 and kwargs.get('boundary')=='commit':
     counts.append(True)
     if len(counts)==1:p._DIALOGUES[self.engine][cid]['deadline']+=1;changed.append(True)
    return result
   return original(cid,protocol,seconds,callback,**transport_options)
  with patch.object(self.engine,'worker_interactive',side_effect=interactive),self.assertRaises(p.Held):self.run_nested()
  self.assertTrue(changed);self.assertFalse(self.worker_final)

 def change_authority_before_worker_guard(self):
  self.unit5();original=self.parent.continuous;module=p._WORKER_MODULES[self.parent];fired=[]
  def continuous():
   result=original()
   if module._ROUND_STATES and not fired:
    before=self.authority.stat();os.utime(self.authority,ns=(before.st_atime_ns,before.st_mtime_ns+1));fired.append(True)
   return result
  self.parent.continuous=continuous
  return fired
 def test_worker_guard_retains_exact_failing_metadata_without_paths(self):
  fired=self.change_authority_before_worker_guard();before=self.authority.read_bytes();stderr=io.StringIO()
  with patch.object(sys,'stderr',stderr),self.assertRaises(p.Held) as caught:self.run_nested()
  self.assertEqual(str(caught.exception.__context__),'worker-parent-final-file')
  self.assertEqual(fired,[True]);self.assertIsNone(self.worker_row);self.assertFalse(self.worker_final)
  self.assertEqual(self.authority.read_bytes(),before)
  detail=p.decode(stderr.getvalue().encode());self.assertLess(len(stderr.getvalue()),1024)
  self.assertNotIn(str(self.authority),stderr.getvalue());self.assertEqual(detail['kind'],'worker-parent-file-change')
  self.assertEqual(detail['path_sha256'],hashlib.sha256(os.fsencode(self.authority)).hexdigest())
  self.assertEqual(detail['current9'],p.nine(self.authority.lstat()));self.assertIn(3,detail['changed_fields'])
  self.assertEqual(detail['current9'][3],detail['original9'][3]+1)
 def test_worker_metadata_diagnostic_failure_preserves_original_refusal(self):
  fired=self.change_authority_before_worker_guard()
  with patch.object(sys.stderr,'write',side_effect=OSError('diagnostic unavailable')),self.assertRaises(p.Held) as caught:self.run_nested()
  self.assertEqual(str(caught.exception.__context__),'worker-parent-final-file')
  self.assertEqual(fired,[True]);self.assertIsNone(self.worker_row);self.assertFalse(self.worker_final)
 def completion_lock(self):
  self.real_spawn=subprocess.Popen
  self.unit5()
  root=self.marker.parent;root.chmod(0o700)
  path=root/'writer-v1.lock';path.write_bytes(b'mylar-media-writer-v1\n');path.chmod(0o600)
  frames=(((str(root),tuple(p.five(root.lstat()))),),((str(path),tuple(p.nine(path.lstat()))),(str(self.marker),tuple(p.nine(self.marker.lstat())))))
  return path,frames
 def competing_lock(self,path):
  program="import fcntl,os,sys;fd=os.open(sys.argv[1],os.O_RDWR);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)"
  with patch.object(p.subprocess,'Popen',self.real_spawn):
   return subprocess.run([sys.executable,'-I','-B','-c',program,str(path)],capture_output=True).returncode
 def kernel_lock_sample(self):
  import fcntl
  path=self.root/'kernel-lock';fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
  self.addCleanup(os.close,fd);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  frame=p.nine(os.fstat(fd))
  return fd,frame
 def test_completion_kernel_accepts_distinct_btrfs_superblock_device(self):
  fd,frame=self.kernel_lock_sample()
  # Btrfs stat reports the subvolume device; fdinfo reports the superblock.
  device='00:00' if frame[0] else '00:01'
  info=f'lock:\t1: FLOCK ADVISORY WRITE {os.getpid()} {device}:{frame[1]} 0 EOF\n'
  with patch('builtins.open',return_value=io.StringIO(info)):
   self.assertTrue(p.completion_fd_locked(fd,frame))
 def test_completion_kernel_device_alias_never_relaxes_other_custody(self):
  fd,frame=self.kernel_lock_sample()
  valid=f'lock:\t1: FLOCK ADVISORY WRITE {os.getpid()} 00:00:{frame[1]} 0 EOF\n'
  variants=[valid.replace(str(os.getpid())+' ',str(os.getpid()+1)+' '),
            valid.replace(':'+str(frame[1])+' ',':'+str(frame[1]+1)+' '),
            valid.replace('FLOCK','POSIX'),valid.replace('WRITE','READ'),
            valid.replace('00:00:','zz:00:'),valid.replace(' 0 EOF',' 1 EOF'),
            valid.replace(' 0 EOF',' 0 10'),'pos:\t0\n','x'*4097]
  for info in variants:
   with self.subTest(info=info[:90]),patch('builtins.open',return_value=io.StringIO(info)):
    self.assertFalse(p.completion_fd_locked(fd,frame))
  for field in (0,1):
   wrong=frame.copy();wrong[field]+=1
   with self.subTest(identity_field=field),patch('builtins.open',return_value=io.StringIO(valid)):
    self.assertFalse(p.completion_fd_locked(fd,wrong))
 def test_completion_exclusion_real_kernel_competitor_and_release(self):
  path,frames=self.completion_lock();lock=p.ArchiveCompletionExclusion(frames)
  try:
   lock.check();self.assertNotEqual(self.competing_lock(path),0)
   self.run_nested();lock.check();self.assertTrue(self.worker_final)
   self.assertNotEqual(self.competing_lock(path),0)
  finally:lock.close()
  self.assertEqual(self.competing_lock(path),0)
 def test_completion_exclusion_contending_writer_refuses_without_wait(self):
  import fcntl
  path,frames=self.completion_lock();fd=os.open(path,os.O_RDWR)
  try:
   fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with self.assertRaisesRegex(p.Held,'native-writer-busy'):p.ArchiveCompletionExclusion(frames)
   self.assertIsNone(self.worker_row)
  finally:os.close(fd)
 def test_completion_exclusion_original_file_drift_refuses(self):
  path,frames=self.completion_lock();os.utime(path,ns=(path.stat().st_atime_ns,path.stat().st_mtime_ns+1))
  with self.assertRaisesRegex(p.Held,'original-FD'):p.ArchiveCompletionExclusion(frames)
  self.assertEqual(self.competing_lock(path),0)
 def test_completion_exclusion_protocol_bytes_refuse(self):
  path,frames=self.completion_lock();path.write_bytes(b'x'*len(b'mylar-media-writer-v1\n'))
  frames=(frames[0],((str(path),tuple(p.nine(path.lstat()))),frames[1][1]))
  with self.assertRaisesRegex(p.Held,'original-protocol'):p.ArchiveCompletionExclusion(frames)
  self.assertEqual(self.competing_lock(path),0)
 def test_completion_exclusion_callback_unlock_refuses(self):
  import fcntl
  path,frames=self.completion_lock();lock=p.ArchiveCompletionExclusion(frames)
  try:
   fcntl.flock(lock.fd,fcntl.LOCK_UN)
   with self.assertRaisesRegex(p.Held,'exclusive-lock-lost'):lock.check()
  finally:
   fd,witness=lock.fd,lock.witness;lock.close();os.close(fd);os.close(witness)
 def test_completion_exclusion_callback_same_inode_reopen_refuses(self):
  import fcntl
  path,frames=self.completion_lock();lock=p.ArchiveCompletionExclusion(frames);fd=lock.fd
  os.close(fd);replacement=os.open(path,os.O_RDWR|os.O_CLOEXEC)
  if replacement!=fd:os.dup2(replacement,fd);os.close(replacement)
  try:
   with self.assertRaises(BlockingIOError):fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with self.assertRaisesRegex(p.Held,'exclusive-lock-lost'):lock.check()
  finally:
   lock.close();os.fstat(fd);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);os.close(fd)
 def test_completion_constructor_root_close_failure_releases_acquired_lock(self):
  import stat
  path,frames=self.completion_lock();real_close=os.close
  def close(fd):
   directory=stat.S_ISDIR(os.fstat(fd).st_mode);real_close(fd)
   if directory:raise OSError('root-close-failure')
  with patch.object(os,'close',close),self.assertRaisesRegex(OSError,'root-close-failure'):
   p.ArchiveCompletionExclusion(frames)
  self.assertEqual(self.competing_lock(path),0)
 def test_completion_constructor_root_close_failure_preserves_busy_refusal(self):
  import stat,fcntl
  path,frames=self.completion_lock();fd=os.open(path,os.O_RDWR);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);real_close=os.close
  def close(other):
   directory=stat.S_ISDIR(os.fstat(other).st_mode);real_close(other)
   if directory:raise OSError('root-close-failure')
  try:
   with patch.object(os,'close',close),self.assertRaisesRegex(p.Held,'native-writer-busy'):
    p.ArchiveCompletionExclusion(frames)
  finally:os.close(fd)
 def test_completion_constructor_independent_close_errors_preserve_root_error(self):
  import stat
  path,frames=self.completion_lock();real_close=os.close
  def close(fd):
   directory=stat.S_ISDIR(os.fstat(fd).st_mode);real_close(fd)
   raise OSError('root-close-failure' if directory else 'lock-close-failure')
  with patch.object(os,'close',close),self.assertRaisesRegex(OSError,'root-close-failure'):
   p.ArchiveCompletionExclusion(frames)
  self.assertEqual(self.competing_lock(path),0)
 def test_completion_constructor_failure_uses_original_cleanup_checker(self):
  path,frames=self.completion_lock();lstat=p.nfs_lstat;kernel=p.completion_fd_locked;foreign=[]
  def changed(path):
   value=lstat(path);p.completion_fd_locked=lambda *args:foreign.append(True)
   return value
  try:
   with patch.object(p,'nfs_lstat',changed),self.assertRaisesRegex(p.Held,'original-kernel-check'):
    p.ArchiveCompletionExclusion(frames)
   self.assertEqual(foreign,[])
  finally:p.completion_fd_locked=kernel
  self.assertEqual(self.competing_lock(path),0)
 def test_late_parent_source_drift_never_releases_producer(self):
  self.unit5();fired=[]
  def change(state):
   if state=='running' and not fired:fired.append(True);Path(self.source['path']).chmod(0o640)
  self.fault=change
  with self.assertRaises(p.Held):self.run_nested()
  self.assertTrue(fired);self.assertFalse(self.worker_final)
 def test_late_catalog_companion_never_releases_producer(self):
  self.unit5();fired=[]
  def change(state):
   if state=='running' and not fired:fired.append(True);Path(str(self.catalog)+'-wal').write_bytes(b'foreign')
  self.fault=change
  with self.assertRaises(p.Held):self.run_nested()
  self.assertTrue(fired);self.assertFalse(self.worker_final)
 def test_producer_registry_removed_during_worker_round_holds(self):
  self.unit5();fired=[]
  def change(state):
   if state=='running' and not fired:fired.append(True);p._DIALOGUES[self.engine].pop('4'*64)
  self.fault=change
  with self.assertRaises(p.Held):self.run_nested()
  self.assertTrue(fired);self.assertFalse(self.worker_final)

 def test_last_worker_FD_callback_original_source_drift_holds(self):
  self.unit5();real=p.os.fstat;fired=[]
  def callback(fd):
   z=real(fd)
   worker=p._DIALOGUES.get(self.engine,{}).get('5'*64)
   if worker is not None and any(fd==v[0] for v in worker['descriptors']) and not fired:
    fired.append(True);Path(self.source['path']).chmod(0o640)
   return z
  with patch.object(p.os,'fstat',callback),self.assertRaises(p.Held):self.run_nested()
  self.assertFalse(fired);self.assertFalse(self.worker_final)
 def test_worker_original_pipe_swap_holds(self):
  self.unit5();fired=[]
  def change(state):
   worker=p._DIALOGUES.get(self.engine,{}).get('5'*64)
   if state=='running' and worker is not None and not fired:
    fired.append(True);worker['descriptors']=p._DIALOGUES[self.engine]['4'*64]['descriptors']
  self.fault=change
  with self.assertRaises(p.Held):self.run_nested()
  self.assertTrue(fired);self.assertFalse(self.worker_final)
 def test_producer_PID_restart_during_worker_round_holds(self):
  self.unit5();fired=[]
  def change(state):
   if state=='running' and not fired:fired.append(True);self.producer_row['State']['Pid']+=1
  self.fault=change
  with self.assertRaises(p.Held):self.run_nested()
  self.assertTrue(fired);self.assertFalse(self.worker_final)
 def test_worker_both_registry_bound_default_disabled(self):
  self.unit5()
  with patch.object(p,'WORKER_OBSERVATION_ENABLED',False),self.assertRaises(p.Held):self.run_nested()
  self.assertFalse(self.worker_final)
 def test_mapped_absent_catalog_claim_late_creation_holds(self):
  self.unit5();fired=[]
  def change(state):
   if state=='running' and not fired:fired.append(True);self.absent.write_bytes(b'late claimed path')
  self.fault=change
  with self.assertRaises(p.Held):self.run_nested()
  self.assertTrue(fired);self.assertFalse(self.worker_final)

 def test_late_complete_protocol_result_mutation_holds(self):
  self.unit5();fired=[];module=p._WORKER_MODULES[self.parent]
  def change(state):
   for protocol in tuple(module._ROUND_STATES):
    if state=='running' and protocol.step==3 and not fired:
     fired.append(True);protocol.result['rights']['cleanup']=True
  self.fault=change
  with self.assertRaises(p.Held):self.run_nested()
  self.assertTrue(fired);self.assertFalse(self.worker_final)

 def test_worker_image_inherited_labels_exact_not_container_labels(self):
  self.unit5();self.run_nested()
  original=self.worker_profile('created');intent=p._WORKER_INTENTS[self.parent]
  self.parent.worker_profile(original,'5'*64,intent,'created')
  for change in ('missing','changed','extra','observer'):
   row=copy.deepcopy(original);labels=row['Config']['Labels']
   if change=='missing':labels.pop('org.opencontainers.image.title')
   elif change=='changed':labels['org.opencontainers.image.title']='foreign'
   elif change=='extra':labels['com.docker.compose.project']='foreign'
   else:labels['com.homelab.reader.worker-observer']='foreign'
   with self.subTest(change=change),self.assertRaises(p.Held):self.parent.worker_profile(row,'5'*64,intent,'created')
  for labels in ({'com.homelab.reader.worker-observer':'inherited-collision'},[],{'label':True}):
   metadata=fixture_ref(self.root/'bad-worker-image.json',p.encode([dict(Id=intent[6],Config={'Labels':labels})]))
   with self.subTest(labels=labels),patch.object(p,'WORKER_OBSERVATION_IMAGE_ORIGINAL',metadata),self.assertRaises(p.Held):self.parent.worker_profile(original,'5'*64,intent,'created')
   Path(metadata['path']).unlink()


if __name__=='__main__':unittest.main()
