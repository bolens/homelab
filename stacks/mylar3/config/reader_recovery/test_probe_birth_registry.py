"""Actual Parent source methods/HostProbe and pipes; owning constructor projected.
No installed Parent, real Docker/NFS/Birth or publication grant is claimed.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import importlib.util,subprocess,threading,unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_gated_host_probe as gate
import comic_nfs_host_probe as h
spec=importlib.util.spec_from_file_location('registry_parent',Path(__file__).with_name('comic_reader_lifecycle_parent.py'));p=importlib.util.module_from_spec(spec);exec(compile(Path(spec.origin).read_bytes(),spec.origin,'exec'),p.__dict__)
class Registry(unittest.TestCase):
 close=gate.Gated.close
 profile=gate.Gated.profile
 engine=gate.Gated.engine
 launch=gate.Gated.launch
 release=gate.Gated.release
 def setUp(self):
  gate.Gated.setUp(self)
  self.owner=object.__new__(p.LifecycleParent);o=self.owner;o.engine=p.ScopedDocker();o.plan={'nonce':'b'*64,'selected_image':self.spec['image']};o.thread=threading.get_ident();o.core=b'projection-not-constructor';o.left=lambda:10
  class Session:
   def close(self):pass
  self.session=Session();self.session.owner=o;self.session.cid='c'*64;self.session.engine_replies=SimpleNamespace();self.session.probe_replies=SimpleNamespace(probe=None)
  class Lease:
   def window_state(self):return 'PREPARED'
   def physical_exit(self):return True
  self.lease=Lease();self.session.lease_replies=SimpleNamespace(lease=self.lease)
  self.modules={'comic_nfs_host_probe.py':h,'comic_nfs_parent_session.py':SimpleNamespace(RetainedChild=Session),'comic_nfs_host_lease.py':SimpleNamespace(HostWriterLease=Lease)};o.nfs_host_modules=lambda:self.modules
  p._NFS_LIVE_SESSIONS[o]=self.session
  self.boundary=object.__new__(h.HostProbe);self.boundary.owner=o;self.boundary.process=self.process;self.boundary.dialogue=self.session.engine_replies;self.boundary.close=self.close;self.session.probe_replies.probe=self.boundary
  self.outer=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.buffer.read()'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  streams=(self.outer.stdin,self.outer.stdout,self.outer.stderr);fds=tuple((v.fileno(),tuple(p.five(p.os.fstat(v.fileno())))) for v in streams);p.dialogue_register(o.engine,self.session.cid,self.outer,streams,fds,p.time.monotonic()+10,self.outer.pid)
  self.addCleanup(self.cleanup)
 def cleanup(self):
  self.outer.stdin.close();self.outer.wait(timeout=3);self.outer.stdout.close();self.outer.stderr.close()
  for registry in (p._NFS_REMOTE_WINDOWS,p._NFS_PROBE_BIRTHS,p._NFS_PROBE_LAUNCHES,p._DIALOGUES,p._DIALOGUE_SEALS):registry.pop(self.owner.engine,None)
  p._NFS_LIVE_SESSIONS.pop(self.owner,None)
 def birth(self):
  self.process.create();self.owner.register_nfs_probe_birth(self.boundary,self.row)
 def start_prepared(self):
  def actual_gate(*args,**kwargs):
   self.assertEqual(args[0],[*p.DOCKER,'start','--attach','--interactive',self.cid])
   return self.launch(self.cid)
  self.process.launcher=self.owner.engine.probe_interactive
  with patch.object(p,'subprocess',SimpleNamespace(Popen=actual_gate,PIPE=subprocess.PIPE)):self.process.start_prepare()
 def test_original_registered_birth_and_consumed_ack_required(self):
  self.birth()
  with self.assertRaises(h.Held):self.owner.begin_nfs_writer_window(self.lease)
  self.assertNotIn(self.owner.engine,p._NFS_REMOTE_WINDOWS)
  self.start_prepared();self.owner.begin_nfs_writer_window(self.lease)
  self.assertIn(self.owner.engine,p._NFS_REMOTE_WINDOWS)
  with self.assertRaisesRegex(p.Held,'no-remote-under-Writer'):self.owner.engine.run(['inspect',self.cid],1)
 def test_lost_prepared_seal_refuses_before_block(self):
  self.birth();self.start_prepared();h._PREPARED_ACKS.pop(self.process)
  with self.assertRaisesRegex(h.Held,'prepared-descriptor'):self.owner.begin_nfs_writer_window(self.lease)
  self.assertNotIn(self.owner.engine,p._NFS_REMOTE_WINDOWS)
 def test_foreign_object_and_repeated_birth_refuse(self):
  self.birth()
  with self.assertRaisesRegex(p.Held,'birth-no-replay'):self.owner.register_nfs_probe_birth(self.boundary,self.row)
  self.session.probe_replies.probe=SimpleNamespace()
  with self.assertRaisesRegex(p.Held,'birth-object'):self.owner.check_nfs_probe_birth(self.cid)
 def test_transport_unregistered_and_blocked_cid_never_launch(self):
  with patch.object(p.subprocess,'Popen',side_effect=AssertionError('unowned launch')) as launch:
   with self.assertRaisesRegex(p.Held,'unregistered-birth'):self.owner.engine.probe_interactive(self.cid)
   p._NFS_REMOTE_WINDOWS[self.owner.engine]=None
   with self.assertRaisesRegex(p.Held,'no-remote-under-Writer'):self.owner.engine.probe_interactive(self.cid)
   launch.assert_not_called()
 def test_transport_uses_exact_registered_cid_and_real_original_pipes(self):
  self.birth();process=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.buffer.read()'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  try:
   with patch.object(p.subprocess,'Popen',return_value=process) as launch:
    returned=self.owner.engine.probe_interactive(self.cid)
    self.assertIs(returned,process);self.assertEqual(launch.call_args.args[0],[*p.DOCKER,'start','--attach','--interactive',self.cid])
    self.assertIs(p._DIALOGUES[self.owner.engine][self.cid]['process'],process)
    with self.assertRaisesRegex(p.Held,'start-no-replay'):self.owner.engine.probe_interactive(self.cid)
  finally:process.stdin.close();process.wait(timeout=3);process.stdout.close();process.stderr.close()
if __name__=='__main__':unittest.main()
