"""Real Popen/flock, projected Docker rows only; no Parent/NFS/kernel grant."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import copy,fcntl,json,os,subprocess,time,unittest
from unittest.mock import patch
import test_host_probe as original
import comic_nfs_host_probe as h
class Gated(unittest.TestCase):
 def setUp(self):
  original.ProbeBoundary.setUp(self);self.block=False;self.started=False;self.client=None
  self.process=h.ProbeProcess(self.spec,['docker'],self.engine,self.close,gated=True,launcher=self.launch)
  self.lock=os.open(Path(self.temp.name)/'writer.lock',os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600);self.addCleanup(os.close,self.lock)
 close=original.ProbeBoundary.close
 profile=original.ProbeBoundary.profile
 def engine(self,argv,**kwargs):
  if self.block:raise ValueError('actual-remote-under-Writer-refused')
  if argv[1]=='create':self.row=self.profile();return subprocess.CompletedProcess(argv,0,(self.cid+'\n').encode(),b'')
  self.assertEqual(argv[1],'inspect');self.calls.append(argv[1]);row=copy.deepcopy(self.row)
  if self.client is not None:
   row['State'].update(Status='running' if self.client.poll() is None else 'exited',Running=self.client.poll() is None,Pid=self.client.pid if self.client.poll() is None else 0,StartedAt='actual-process-projection',ExitCode=0)
  return subprocess.CompletedProcess(argv,0,json.dumps([row]).encode(),b'')
 def launch(self,cid):
  self.assertFalse(self.block);self.assertEqual(cid,self.cid)
  source=Path(__file__).with_name('comic_negative_nfs_hardlink_child.py')
  code="import runpy,json;g=runpy.run_path("+repr(str(source))+",run_name='fixture_gate');g['wait_original_execute']("+repr(self.spec['input_sha256'])+",3,"+repr(self.spec['probe_sha256'])+");print(json.dumps({'fixture_kernel_not_executed':True}),flush=True)"
  self.client=subprocess.Popen([sys.executable,'-I','-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);self.addCleanup(self.release);return self.client
 def release(self):
  if self.client is not None:
   if self.client.poll() is None:self.client.stdin.close();self.client.wait(timeout=5)
   for x in (self.client.stdin,self.client.stdout,self.client.stderr):
    if not x.closed:x.close()
 def test_prelease_real_pipe_held_execution_no_remote_postrelease_terminal(self):
  self.process.create();self.process.start_prepare();before=len(self.calls)
  fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB);self.block=True
  try:
   result=self.process.execute_local();self.assertTrue(result['kernel_finished']);self.assertFalse(result['terminal_profile_verified']);self.assertEqual(len(self.calls),before)
   with self.assertRaisesRegex(ValueError,'actual-remote-under-Writer-refused'):self.process.finish_after_release()
  finally:self.block=False;fcntl.flock(self.lock,fcntl.LOCK_UN)
  result=self.process.finish_after_release();self.assertEqual(result['profile']['State']['Status'],'exited');self.assertTrue(self.process.terminal)
 def test_no_second_execute_or_opaque_client_substitution(self):
  self.process.create();self.process.start_prepare();self.process.execute_local()
  with self.assertRaisesRegex(h.Held,'execute-no-replay'):self.process.execute_local()
  self.process.pid_original+=1
  with self.assertRaisesRegex(h.Held,'process-seal'):self.process.local()
 def test_prepared_descriptor_requires_consumed_original_ack(self):
  self.process.create();created=self.row
  boundary=h.HostProbe.__new__(h.HostProbe);boundary.process=self.process;boundary.close=self.close
  birth=h.HostProbe.birth_descriptor(boundary,created)
  self.assertEqual(set(birth),{'cid','name','spec','static','profile'});self.assertEqual(birth['cid'],self.cid)
  with self.assertRaises(h.Held):h.HostProbe.prepared_descriptor(boundary)
  self.process.start_prepare();value=h.HostProbe.prepared_descriptor(boundary)
  self.assertEqual(set(value),{'cid','name','spec','static','process_pid','process_start_ticks','inner_epoch','pipes','native_grant','publication_authority'})
  self.assertEqual(value['process_pid'],self.client.pid);self.assertEqual(value['pipes'],[[fd,list(v)] for fd,v in self.process.pipe_original]);self.assertFalse(value['native_grant'])
  h._PREPARED_ACKS.pop(self.process)
  with self.assertRaisesRegex(h.Held,'prepared-descriptor'):h.HostProbe.prepared_descriptor(boundary)
 def test_gated_probe_cannot_use_legacy_docker_start(self):
  self.process.create();before=len(self.calls)
  with self.assertRaisesRegex(h.Held,'start-no-replay'):self.process.start()
  self.assertEqual(len(self.calls),before)
class AttachDrain(unittest.TestCase):
 """Real inner exit and a live attach client blocked on its original FIFO."""
 def setUp(self):
  original.ProbeBoundary.setUp(self)
  self.client=None;self.inner_pid=None;self.block=False;self.draining=None
  self.marker=Path(self.temp.name)/'inner-exited'
 close_original=original.ProbeBoundary.close
 profile=original.ProbeBoundary.profile
 def close(self):
  self.close_original()
  if self.process.execution_sent:
   end=time.monotonic()+5
   while not self.marker.exists():
    self.assertLess(time.monotonic(),end,'owned inner did not finish');time.sleep(0.001)
   if self.draining is None:
    self.assertIsNone(self.client.poll())
    with self.assertRaises(FileNotFoundError):h.ticks(self.inner_pid)
    self.draining=True
 def engine(self,argv,**kwargs):
  if self.block:raise ValueError('remote-under-Writer-refused')
  if argv[1]=='create':self.row=self.profile();return subprocess.CompletedProcess(argv,0,(self.cid+'\n').encode(),b'')
  self.assertEqual(argv[1],'inspect');self.calls.append('inspect');row=copy.deepcopy(self.row)
  if self.client is not None:
   running=self.client.poll() is None
   row['State'].update(Status='running' if running else 'exited',Running=running,Pid=self.inner_pid if running else 0,StartedAt='actual-inner-projection',ExitCode=self.client.returncode or 0)
  return subprocess.CompletedProcess(argv,0,json.dumps([row]).encode(),b'')
 def pair(self,exitcode=0):
  def launch(cid):
   self.assertEqual(cid,self.cid)
   source=Path(__file__).with_name('comic_negative_nfs_hardlink_child.py')
   inner="import runpy,json;g=runpy.run_path("+repr(str(source))+",run_name='fixture_gate');g['wait_original_execute']("+repr(self.spec['input_sha256'])+",5,"+repr(self.spec['probe_sha256'])+");print(json.dumps({'fixture_kernel_not_executed':True,'padding':'x'*32768}),flush=True);raise SystemExit("+str(exitcode)+")"
   client="import subprocess,sys;from pathlib import Path;p=subprocess.Popen([sys.executable,'-I','-B','-u','-c',"+repr(inner)+"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);print(p.pid,flush=True);sys.stdout.buffer.write(p.stdout.readline());sys.stdout.buffer.flush();command=sys.stdin.buffer.readline();out,err=p.communicate(command,timeout=6);Path("+repr(str(self.marker))+").write_text('exited');sys.stdout.buffer.write(out);sys.stdout.buffer.flush();sys.stderr.buffer.write(err);raise SystemExit(p.returncode)"
   self.client=subprocess.Popen([sys.executable,'-I','-B','-u','-c',client],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   self.addCleanup(self.release)
   fcntl.fcntl(self.client.stdout.fileno(),fcntl.F_SETPIPE_SZ,4096)
   self.assertEqual(fcntl.fcntl(self.client.stdout.fileno(),fcntl.F_GETPIPE_SZ),4096)
   self.inner_pid=int(self.client.stdout.readline());return self.client
  self.process=h.ProbeProcess(self.spec,['docker'],self.engine,self.close,gated=True,launcher=launch)
  self.process.create();self.process.start_prepare()
 def release(self):
  if self.client is not None:
   try:self.client.communicate(timeout=7)
   except subprocess.TimeoutExpired:self.client.kill();self.client.communicate(timeout=3)
   for stream in (self.client.stdin,self.client.stdout,self.client.stderr):
    if not stream.closed:stream.close()
 def test_exited_inner_drains_original_live_client_before_waiting_for_exit(self):
  self.pair();before=len(self.calls);self.block=True
  try:result=self.process.execute_local()
  finally:self.block=False
  self.assertTrue(self.draining);self.assertTrue(result['local_exit_verified']);self.assertFalse(result['terminal_profile_verified']);self.assertEqual(len(self.calls),before)
  self.assertEqual(self.client.returncode,0)
  self.assertTrue(self.process.finish_after_release()['profile']['State']['Status']=='exited')
 def test_nonzero_attach_exit_cannot_complete(self):
  self.pair(exitcode=7)
  with self.assertRaisesRegex(h.Held,'inner-exit-unknown|local-exit'):self.process.execute_local()
  self.assertFalse(self.process.terminal)
 def test_foreign_client_start_tick_refuses_drain(self):
  self.pair();ticks=h.ticks
  def foreign(pid):return ticks(pid)+1 if pid==self.client.pid and self.process.execution_sent else ticks(pid)
  with patch.object(h,'ticks',side_effect=foreign),self.assertRaisesRegex(h.Held,'inner-exit-unknown'):self.process.execute_local()
 def test_inner_disappearance_before_execute_refuses(self):
  self.pair();ticks=h.ticks
  def absent(pid):
   if pid==self.inner_pid:raise FileNotFoundError()
   return ticks(pid)
  with patch.object(h,'ticks',side_effect=absent),self.assertRaisesRegex(h.Held,'inner-exit-unknown'):self.process.local()
 def test_substituted_stdout_fifo_refuses(self):
  self.pair();saved=self.client.stdout;r,w=os.pipe()
  try:
   self.client.stdout=os.fdopen(r,'rb')
   with self.assertRaisesRegex(h.Held,'original-FIFOs'):self.process.local()
  finally:self.client.stdout.close();self.client.stdout=saved;os.close(w)
if __name__=='__main__':unittest.main()
