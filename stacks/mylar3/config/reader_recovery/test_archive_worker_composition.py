"""Actual nested Popen/OS pipes and SQLite; Docker/profile/birth are labelled fixtures.

No container/runtime/image/mount or protected-cap acceptance is claimed here.
"""
import copy
from contextlib import closing
import hashlib
import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import sys
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
  self.setup();x=self.parent;x.plan.update(version=12,native={'data':str(self.root),'roots':[str(self.root)]})
  self.archive=self.root/'Comic.cbz';self.archive.write_bytes(b'preserved fixture archive bytes')
  self.catalog=self.root/'mylar.db';self.authority=self.root/'workflow.sqlite';writer=self.root/'media-writer';writer.mkdir();self.marker=writer/'publication-v1.json';self.marker.write_bytes(b'{}')
  with closing(sqlite3.connect(self.catalog)) as db,db:
   db.execute('CREATE TABLE comics(ComicID TEXT,ComicLocation TEXT)');db.execute('CREATE TABLE issues(IssueID TEXT,ComicID TEXT,Location TEXT,Status TEXT)');db.execute('CREATE TABLE annuals(IssueID TEXT,ComicID TEXT,ReleaseComicID TEXT,Location TEXT,Status TEXT,Deleted INT)')
   db.execute('INSERT INTO comics VALUES(?,?)',('456',str(self.root)));db.execute('INSERT INTO issues VALUES(?,?,?,?)',('123','456','Comic.cbz','Downloaded'))
  with closing(sqlite3.connect(self.authority)) as db,db:db.execute('CREATE TABLE records(k TEXT,v TEXT)')
  spec=importlib.util.spec_from_file_location('unit5_actual_pure_vectors',HERE/'comic_archive_worker_vectors.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  # Source-owned host fixture selectors; neither __file__ nor SDK types change.
  module.READ_ROOTS=(str(self.root),);module.SOURCE_ENTRY=str(WORKER)
  p._WORKER_MODULES[x]=module
  p._WORKER_FUNCTIONS[x]=(tuple((n,module.__dict__[n],module.__dict__[n].__code__) for n in ('need','encode','decode','digest','path','put','frame','pack','mapping','freeze','response')),module.Round,tuple(module.Round.__dict__.items()),module.Round.__init__.__code__,module.Round.accept.__code__)
  sha=hashlib.sha256(WORKER.read_bytes()).hexdigest();x.plan['worker_observation']={'mode':'original-pipes-v1','source':{'path':str(WORKER),'sha256':sha,'signature9':p.nine(WORKER.lstat())},'image_sources':{}}
  x.baselines={'held_worker':{'Image':'sha256:'+'7'*64}};x.baselines['held_worker']['Mounts']=[dict(Type='bind',Source=str(self.root),Destination=str(self.root),RW=True)]
  rolepaths={'archive':self.archive,'catalog':self.catalog,'authority':self.authority,'marker':self.marker};roles={k:dict(path=str(v),signature9=p.nine(v.lstat()),sha256=hashlib.sha256(v.read_bytes()).hexdigest()) for k,v in rolepaths.items()};roles['catalog_native_target']=str(self.archive)
  terminal=p.decode(Path(self.terminal['path']).read_bytes());terminal['worker_roles']=roles;terminal['independent_observation']['source_sha256']=roles['archive']['sha256']
  terminal['original_vectors']['files'] += [[str(v),p.nine(v.lstat())] for v in rolepaths.values()]
  nodes={str(n):p.five(n.lstat()) for v in rolepaths.values() for n in v.parents};terminal['original_vectors']['nodes'] += list(nodes.items())
  terminal['original_vectors']['absent'] += [str(v)+s for v in (self.catalog,self.authority) for s in ('-journal','-wal','-shm')]
  self.terminal=fixture_ref(Path(self.terminal['path']),p.encode(terminal));self.refs['terminal_report']=self.terminal;self.message['terminal']['terminal_report']=self.terminal
  er=Path(self.refs['execution_report']['path']);execute=p.decode(er.read_bytes());execute['terminal_report']=self.terminal;self.refs['execution_report']=fixture_ref(er,p.encode(execute));self.message['terminal']['execution_report']=self.refs['execution_report']
  self.producer_row=copy.deepcopy(self.current);self.worker_row=None;self.worker_process=None;self.engine=p.ScopedDocker();x.engine=self.engine
  self.processes=[];self.both=[];self.fault=None;self.worker_final=False
  real=subprocess.Popen
  producer_script="import sys,json;message=json.loads(sys.argv[1]);print(json.dumps(message,sort_keys=True,separators=(',',':')),flush=True);reply=sys.stdin.buffer.readline();assert json.loads(reply)['type']=='terminal-release';print(json.dumps({'type':'ACK','ack':{'fixture':'synthetic-parent-facts-only'}},sort_keys=True,separators=(',',':')),flush=True)"
  worker_script="import importlib.util,sys;path=sys.argv[1];root=sys.argv[2];args=sys.argv[3:];s=importlib.util.spec_from_file_location('actual_worker_entry',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.READ_ROOTS=(root,);sys.argv=[path,*args];m.main()"
  def spawn(args,**kw):
   cid=args[-1]
   if cid=='4'*64:
    proc=real([sys.executable,'-I','-B','-c',producer_script,p.encode(self.message).decode()],**kw);self.producer_row['State']['Pid']=proc.pid
   else:
    intent=p._WORKER_INTENTS[x];cmd=list(intent[1]);proc=real([sys.executable,'-I','-B','-c',worker_script,str(WORKER),str(self.root),*cmd[3:]],**kw);self.worker_process=proc
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
  return dict(Id='5'*64,Image=image,Name=name,Path='python3',Args=list(cmd),Config=dict(User='1000:1000',Entrypoint=['python3'],Cmd=list(cmd),OpenStdin=True,Tty=False,Labels={'com.homelab.reader.worker-observer':name}),HostConfig=host,Mounts=[dict(Type='bind',Source=a,Destination=b,RW=False) for a,b in mounts],NetworkSettings={},State=status)
 def run_nested(self):
  def handler(value,raw=None):
   if value is None:return None
   return self.parent.accept_archive_terminal(self.proof,[],value,copy.deepcopy(self.producer_row),copy.deepcopy(self.producer_row),raw)
  return self.engine.interactive('4'*64,handler,10)
 def test_genuine_nested_original_pipes_worker_readback_before_producer_release(self):
  self.unit5();ack=self.run_nested();self.assertEqual(ack,{'fixture':'synthetic-parent-facts-only'});self.assertTrue(self.both);self.assertTrue(self.worker_final)
  result=p._ARCHIVE_TERMINAL_ROUNDS[self.parent]['worker_result'];self.assertEqual(result['type'],'observed');self.assertTrue(all(v is False for v in result['rights'].values()))
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
  self.assertTrue(fired);self.assertFalse(self.worker_final)
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

if __name__=='__main__':unittest.main()
