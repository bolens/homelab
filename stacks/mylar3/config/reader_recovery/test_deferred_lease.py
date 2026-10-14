"""Genuine Writer/Popen/FIFO acquisition gate; no Docker/Parent authority."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import fcntl,json,os,subprocess,unittest
import test_host_lease as t
class Deferred(t.RealLease):
 def prepared(self,seconds=3):
  helper=Path(__file__).with_name('comic_negative_nfs_active_lifecycle.py')
  p=subprocess.Popen([sys.executable,'-I','-B',str(helper),'--lease-child','--writer-source',str(t.WRITER),'--writer-sha256',t.SHA,'--writer-root',str(self.root),'--token','a'*64,'--lease-seconds',str(seconds),'--defer-acquire'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);self.processes.append(p)
  c=t.m.LeaseChannel(p,'a'*64,self.root,t.SHA,10);ack=c.receive('prepared');self.assertFalse(ack['native_grant']);self.assertFalse(ack['publication_authority']);return c
 def command(self,c,token='a'*64):
  c.process.stdin.write((json.dumps({'token':token,'action':'acquire','owned_absence_verified':False})+'\n').encode());c.process.stdin.flush()
 def free(self):
  fd=os.open(self.root/'writer-v1.lock',os.O_RDWR)
  try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
  finally:os.close(fd)
 def test_prepared_has_no_lock_until_original_acquire_then_releases(self):
  c=self.prepared();self.free();self.command(c);c.receive('held')
  fd=os.open(self.root/'writer-v1.lock',os.O_RDWR)
  try:
   with self.assertRaises(BlockingIOError):fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  finally:os.close(fd)
  c.release(());self.free();self.assertTrue(c.released)
 def test_wrong_token_never_acquires_or_acknowledges(self):
  c=self.prepared();self.command(c,'b'*64);self.assertNotEqual(c.process.wait(timeout=4),0);self.assertEqual(c.process.stdout.read(),b'');self.assertIn(b'lease-original-acquire-command',c.process.stderr.read());self.free()
 def test_prepared_eof_never_acquires(self):
  c=self.prepared();c.process.stdin.close();self.assertNotEqual(c.process.wait(timeout=4),0);self.assertEqual(c.process.stdout.read(),b'');self.free()
 def test_prepared_wait_uses_original_total_deadline(self):
  c=self.prepared(1);self.assertNotEqual(c.process.wait(timeout=2),0);self.assertEqual(c.process.stdout.read(),b'');self.assertIn(b'lease-original-deadline',c.process.stderr.read());self.free()
if __name__=='__main__':unittest.main()
