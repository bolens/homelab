"""Original Popen stdin gate only; kernel/NFS/factory not substituted or executed."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,unittest
class Gate(unittest.TestCase):
 def launch(self,seconds=3):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.marker=Path(self.tmp.name)/'executed'
  source=Path(__file__).with_name('comic_negative_nfs_hardlink_child.py')
  code="import runpy,os;from pathlib import Path;m=runpy.run_path("+repr(str(source))+",run_name='source_gate_fixture');m['wait_original_execute']('a'*64,"+str(seconds)+",'b'*64);fd=os.open("+repr(str(self.marker))+",os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,b'executed');os.close(fd)"
  p=subprocess.Popen([sys.executable,'-I','-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);self.addCleanup(self.finish,p)
  ack=json.loads(p.stdout.readline());self.assertEqual(ack['state'],'prepared');self.assertFalse(ack['native_grant']);self.assertFalse(self.marker.exists());return p
 def finish(self,p):
  if p.poll() is None:p.stdin.close();p.wait(timeout=5)
  for s in (p.stdin,p.stdout,p.stderr):
   if not s.closed:s.close()
 def test_original_stdin_token_unblocks_only_once(self):
  p=self.launch();p.stdin.write((json.dumps({'token':'a'*64,'operation':'execute'})+'\n').encode());p.stdin.flush();self.assertEqual(p.wait(timeout=5),0);self.assertEqual(self.marker.read_bytes(),b'executed')
 def test_foreign_token_refuses_without_execution(self):
  p=self.launch();p.stdin.write((json.dumps({'token':'c'*64,'operation':'execute'})+'\n').encode());p.stdin.flush();self.assertNotEqual(p.wait(timeout=5),0);self.assertFalse(self.marker.exists());self.assertIn(b'probe-original-gate-command',p.stderr.read())
 def test_original_eof_refuses_without_execution(self):
  p=self.launch();p.stdin.close();self.assertNotEqual(p.wait(timeout=5),0);self.assertFalse(self.marker.exists())
 def test_original_gate_deadline_refuses_without_execution(self):
  p=self.launch(1);self.assertNotEqual(p.wait(timeout=2),0);self.assertFalse(self.marker.exists());self.assertIn(b'probe-original-gate-deadline',p.stderr.read())
if __name__=='__main__':unittest.main()
