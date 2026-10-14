"""Real Popen/flock, projected Docker rows only; no Parent/NFS/kernel grant."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import copy,fcntl,json,os,subprocess,unittest
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
if __name__=='__main__':unittest.main()
