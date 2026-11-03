"""Original Popen stdin gate only; kernel/NFS/factory not substituted or executed."""
from pathlib import Path
import json,subprocess,sys,tempfile,unittest
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

class BindingTransport(unittest.TestCase):
 def setUp(self):
  import importlib.util,hashlib
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  source=Path(__file__).with_name('comic_negative_nfs_hardlink_child.py')
  spec=importlib.util.spec_from_file_location('binding_child_fixture',source);self.child=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.child)
  self.source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
  self.binding=dict(host_root='/host/live-retention',child_root='/host/live-retention',root5=[1,2,16832,1000,1000])
  self.kernel=self.root/'kernel.py';self.kernel.write_text("import json\nEXPECTED="+repr(self.binding)+"\ndef observe_namespace(plan,*,expected_binding=None):\n assert expected_binding==EXPECTED,'missing-in-first-observation'\n return {'fixture_namespace_only':True}\ndef run(*args,namespace=None,expected_binding=None):\n assert namespace=={'fixture_namespace_only':True} and expected_binding==EXPECTED,'missing-in-kernel-reobservation'\n raise RuntimeError('binding-forwarded-to-both-stages')\n")
  self.input=self.root/'input.json';self.input.write_text(json.dumps(dict(seconds=120)))
  self.kernel_sha=hashlib.sha256(self.kernel.read_bytes()).hexdigest();self.input_sha=hashlib.sha256(self.input.read_bytes()).hexdigest()
 def call(self,gate):
  from unittest.mock import patch
  with patch.object(self.child,'KERNEL_SHA',self.kernel_sha),patch.object(self.child,'wait_original_execute',side_effect=gate):
   return self.child.run(str(self.input),self.input_sha,self.source_sha,str(self.kernel),defer_execute=True,retention_binding=self.binding)
 def test_original_binding_reaches_both_namespace_stages(self):
  with self.assertRaisesRegex(RuntimeError,'binding-forwarded-to-both-stages'):self.call(lambda *a,**k:None)
 def test_post_ACK_binding_mutation_refuses_before_kernel(self):
  def mutate(*args,**kwargs):self.binding['root5'][1]+=1
  with self.assertRaisesRegex(ValueError,'binding-tape'):self.call(mutate)
 def test_binding_without_original_gate_refuses_before_source_reads(self):
  from unittest.mock import patch
  def forbidden(*args,**kwargs):raise AssertionError('Read before gate admission')
  with patch.object(self.child.os,'lstat',side_effect=forbidden),self.assertRaisesRegex(ValueError,'binding-needs-gate'):
   self.child.run('/missing','a'*64,'b'*64,'/missing',retention_binding=self.binding)

if __name__=='__main__':unittest.main()
