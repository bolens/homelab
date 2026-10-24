"""Actual method + Writer/Popen projection; Parent constructor/Docker remain false."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import fcntl,os,subprocess,types,unittest
import test_host_lease as t
class Projection:pass
class Window(t.RealLease):
 def window(self,actual=False):
  helper=Path(__file__).with_name('comic_negative_nfs_active_lifecycle.py');p=subprocess.Popen([sys.executable,'-I','-B',str(helper),'--lease-child','--writer-source',str(t.WRITER),'--writer-sha256',t.SHA,'--writer-root',str(self.root),'--token','a'*64,'--lease-seconds','5','--defer-acquire'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);self.processes.append(p);c=t.m.LeaseChannel(p,'a'*64,self.root,t.SHA,10);c.receive('prepared')
  lease=object.__new__(t.m.HostWriterLease) if actual else Projection();lease.channel=c;lease.process=p;lease.cid=lease.cid_original='c'*64;lease.epoch=(p.pid,'actual-helper-projection');lease.runtime_pid=p.pid;lease.runtime_ticks=t.m.ticks(p.pid);lease.token='a'*64;lease.original=lambda **kwargs:c.raw()
  for name in ('window_state','physical_exit','local_running','acquire','check'):
   setattr(lease,name,types.MethodType(getattr(t.m.HostWriterLease,name),lease))
  seal=(lease.cid_original,p,c,lease.epoch,lease.runtime_pid,lease.runtime_ticks);t.m._WINDOWS[lease]=('PREPARED',seal)
  owner=Projection();owner.blocked=False;owner.remote_calls=0
  def begin(value):
   self.assertIs(value,lease);self.assertEqual(lease.window_state(),'PREPARED');self.free();owner.blocked=True
  def end(value):
   self.assertIs(value,lease);self.assertIs(lease.physical_exit(),True);owner.blocked=False
  def remote():
   owner.remote_calls+=1
   if owner.blocked:raise ValueError('remote-under-original-Writer')
  owner.begin_nfs_writer_window=begin;owner.end_nfs_writer_window=end;owner.inspect=remote;lease.owner=owner;return lease,owner
 def free(self):
  fd=os.open(self.root/'writer-v1.lock',os.O_RDWR)
  try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
  finally:os.close(fd)
 def test_actual_check_held_performs_no_remote_profile_and_original_lock_busy(self):
  lease,owner=self.window();lease.acquire();self.assertTrue(owner.blocked);self.assertEqual(lease.window_state(),'HELD')
  with self.assertRaises(BlockingIOError):self.free()
  for _ in range(3):self.assertTrue(lease.check()['held'])
  self.assertEqual(owner.remote_calls,0)
  with self.assertRaisesRegex(ValueError,'remote-under-original-Writer'):owner.inspect()
  lease.channel.release(());seal=t.m._WINDOWS[lease][1];t.m._WINDOWS[lease]=('RELEASED_PHYSICAL',seal);owner.end_nfs_writer_window(lease);self.assertFalse(owner.blocked);self.free()
 def test_release_ack_alone_does_not_grant_physical_exit(self):
  lease,owner=self.window();lease.acquire()
  with self.assertRaisesRegex(t.m.Held,'physical-exit-required'):lease.physical_exit()
  self.assertTrue(owner.blocked);self.assertEqual(owner.remote_calls,0)
  lease.channel.release(())
 def test_proven_eof_exit_clears_only_physical_block_without_release_ACK(self):
  lease,owner=self.window();lease.acquire();seal=t.m._WINDOWS[lease][1]
  lease.channel.abort_original();self.assertFalse(lease.channel.released)
  t.m._WINDOWS[lease]=('RELEASED_PHYSICAL',seal);owner.end_nfs_writer_window(lease)
  self.assertFalse(owner.blocked);self.assertIs(lease.physical_exit(),True);self.free()
 def test_released_window_inner_pid_substitution_refuses(self):
  lease,owner=self.window();lease.acquire();seal=t.m._WINDOWS[lease][1];lease.channel.release(())
  t.m._WINDOWS[lease]=('RELEASED_PHYSICAL',seal);lease.runtime_pid+=1
  with self.assertRaisesRegex(t.m.Held,'physical-original-window-seal'):lease.physical_exit()
  self.assertTrue(owner.blocked)
 def test_owned_pulse_retains_real_helper_ACK_and_Writer_lock(self):
  lease,owner=self.window(actual=True);lease.acquire()
  self.assertEqual(lease._pulse_owned()['state'],'held')
  with self.assertRaises(BlockingIOError):self.free()
  self.assertEqual(owner.remote_calls,0);lease.channel.release(())
 def test_owned_pulse_refuses_actual_replaced_FIFO_before_write(self):
  lease,owner=self.window(actual=True);lease.acquire();r,w=os.pipe()
  try:
   os.dup2(r,lease.channel.fds[0][0])
   with self.assertRaises(t.m.Held):lease._pulse_owned()
   self.assertTrue(owner.blocked)
  finally:os.close(r);os.close(w)
 def test_owned_pulse_refuses_window_change_after_real_ACK(self):
  lease,owner=self.window(actual=True);lease.acquire();receive=lease.channel.receive
  def changed(state):
   result=receive(state);lease.cid='d'*64;return result
  lease.channel.receive=changed
  with self.assertRaisesRegex(t.m.Held,'pulse-original-window-seal'):lease._pulse_owned()
  self.assertTrue(owner.blocked);lease.channel.receive=receive;lease.channel.release(())
if __name__=='__main__':unittest.main()
