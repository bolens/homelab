"""Connected host runtime only: real producer reports/ACK and Parent/worker dialogue.

Initial admission/Scope/Birth/Docker profiles are explicit existing fixtures.
No image, NFS, protected Parent custody, restart or live acceptance is claimed.
"""
import copy,hashlib,json,subprocess,sys,unittest,tempfile,importlib.util
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).parent;CONFIG=HERE;RECOVERY=HERE/'reader_recovery';SUPPLIER=RECOVERY/'_archive_connected_fixtures';sys.path.insert(0,str(RECOVERY))
import test_archive_worker_composition as host
from test_reader_lifecycle_parent import fixture_ref
p=host.p
REAL_POPEN=subprocess.Popen
class Connected(unittest.TestCase):
 setUp=host.Tests.setUp
 setup=host.Tests.setup
 unit5=host.Tests.unit5
 worker_profile=host.Tests.worker_profile
 def connected(self,fault=None):
  self.unit5();self.retained_checks=[];x=self.parent
  out=x.op/'execute'
  for node in out.iterdir():node.unlink()
  native=self.root/'actual-native-fixtures';native.mkdir(mode=0o700)
  worker_spawn=subprocess.Popen
  def spawn(args,**kw):
   if args[-1]=='4'*64:
    proc=REAL_POPEN([sys.executable,'-I','-B',str(SUPPLIER/'producer.py'),str(out),str(native)],**kw);self.producer_row['State']['Pid']=proc.pid;self.processes.append(proc);return proc
   return worker_spawn(args,**kw)
  source=RECOVERY/'comic_archive_repair_action.py';self.provider_sha=hashlib.sha256(source.read_bytes()).hexdigest()
  def handler(message,raw=None):
   if message is None:return None
   # Original admission remains a labelled host fixture; populate its expected
   # owner from the actual owning producer record, never synthesize a report.
   terminal=p.decode(Path(message['terminal']['terminal_report']['path']).read_bytes());self.assert_original_retained()
   request=dict(version=1,owner=terminal['owner'],operation_id=terminal['operation_id'])
   x.plan['producer_inputs']['archive_request']=fixture_ref(self.root/'request.json',p.encode(request))
   x.plan['native']=dict(data=str(Path(terminal['worker_roles']['catalog']['path']).parent),roots=[str(Path(terminal['worker_roles']['archive']['path']).parent)]);x.plan['nonce']=message['nonce'];x.plan['mounts'].append(dict(host=str(CONFIG),child=str(CONFIG),write=False))
   x.mapping=p.Paths(x.plan['mounts']);x.core=p.encode(dict(plan=x.plan,files=x.files,nodes=x.nodes,source=x.source_ref,input=x.plan_ref,engine=id(x.engine),thread=x.thread,deadline=x.deadline));p._CORES[x]=x.core
   if fault=='terminal':
    target=Path(message['terminal']['terminal_report']['path']);target.chmod(0o640)
   reply=x.accept_archive_terminal(self.proof,[],message,copy.deepcopy(self.producer_row),copy.deepcopy(self.producer_row),raw)
   self.assert_original_retained()
   if fault=='lost-response':return None
   return reply
  self.actual_ACKs=[];original_decode=p.decode
  def decode(raw):
   value=original_decode(raw)
   if type(value)is dict and value.get('type')=='ACK':self.actual_ACKs.append(value)
   return value
  with patch.object(p.subprocess,'Popen',spawn),patch.object(p,'decode',decode):
   return self.engine.interactive('4'*64,handler,15)
 def assert_original_retained(self):
  original=json.loads((self.root/'actual-native-fixtures/fixture-original.json').read_bytes())
  self.assertEqual(hashlib.sha256(Path(original['retained_original']).read_bytes()).hexdigest(),original['original_sha256'])
  self.assertNotEqual(hashlib.sha256(Path(original['new_archive']).read_bytes()).hexdigest(),original['original_sha256']);self.retained_checks.append(True)
 def test_connected_actual_reports_release_worker_and_ACK(self):
  ack=self.connected();self.assertEqual(self.actual_ACKs,[dict(type='ACK',ack=ack)]);self.assertEqual(self.retained_checks,[True,True]);self.assertNotIn('fixture',ack);self.assertFalse(ack['publication_acceptance']);self.assertFalse(ack['reader_resume_authority'])
  report=p.validate_ack({k:v for k,v in ack.items()if k!='terminal_release'},'execute',self.parent.plan['nonce'],self.provider_sha)
  record=p._ARCHIVE_TERMINAL_ROUNDS[self.parent];self.assertEqual(set(ack),{'nonce','phase','source_sha256','report','publication_acceptance','reader_resume_authority','terminal_release'});self.assertEqual(ack['terminal_release'],dict(sequence=record['sequence'],conversation_sequence=record['sequence'],challenge=record['challenge'],request_sha256=record['request_sha256'],response_sha256=record['response_sha256']));self.assertEqual(record['refs']['execution_report'],report);self.assertTrue(self.worker_final);self.assertTrue(self.both)
  self.assertEqual(record['worker_result']['type'],'observed');self.assertTrue(all(value is False for value in record['worker_result']['rights'].values()))
 def test_lost_release_retains_real_reports_and_original_no_ACK(self):
  with self.assertRaisesRegex(p.Held,'child-uncertain-proof-retained'):self.connected('lost-response')
  self.assertEqual(self.actual_ACKs,[]);self.assertEqual(self.retained_checks,[True,True]);record=p._ARCHIVE_TERMINAL_ROUNDS[self.parent];self.assertEqual(record['worker_result']['type'],'observed')
  self.assertTrue(all(Path(ref['path']).is_file()for ref in record['refs'].values()))
  self.assertFalse(record['execute']['publication_acceptance']);self.assertFalse(record['execute']['automatic_replay'])
  producer=self.processes[0];producer.wait(timeout=3);self.assertNotEqual(producer.returncode,0)
 def test_real_terminal_tamper_never_releases_or_ACKs(self):
  with self.assertRaisesRegex(p.Held,'child-uncertain-proof-retained'):self.connected('terminal')
  self.assertEqual(self.actual_ACKs,[]);self.assertEqual(self.retained_checks,[True]);self.assertNotIn(self.parent,p._ARCHIVE_TERMINAL_ROUNDS);self.assertFalse(self.worker_final)
  self.assertEqual({n.name for n in (self.parent.op/'execute').iterdir()},{'execution-originals.json','execute-report.json','terminal-report.json'})
  producer=self.processes[0];producer.wait(timeout=3);self.assertNotEqual(producer.returncode,0)
 def test_genuine_preimage_producer_reproduces_fixed_output_defect(self):
  self.assertEqual(hashlib.sha256((SUPPLIER/'action_preimage.py').read_bytes()).hexdigest(),'e5e6ea45a26dcb5ef5569b49d5e9767ebb30ef9c858b909b779f8c9d93906e59')
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);out=root/'execute';out.mkdir(mode=0o700);native=root/'native';native.mkdir(mode=0o700)
   result=subprocess.run([sys.executable,'-I','-B',str(SUPPLIER/'producer.py'),str(out),str(native),'preimage'],input=b'',capture_output=True,timeout=15)
   self.assertNotEqual(result.returncode,0);self.assertIn(b'repair-fixed-output',result.stderr);self.assertEqual(result.stdout,b'');self.assertEqual({n.name for n in out.iterdir()},{'execution-originals.json'})
 def test_terminal_output_is_fixed_phase_and_census(self):
  spec=importlib.util.spec_from_file_location('fixed_action',RECOVERY/'comic_archive_repair_action.py');action=importlib.util.module_from_spec(spec);spec.loader.exec_module(action)
  with tempfile.TemporaryDirectory()as tmp:
   out=Path(tmp);out.chmod(0o700)
   for names in ((),('foreign',),['execution-originals.json']):
    with self.assertRaisesRegex(action.Held,'repair-fixed-output'):action.emit(out,'terminal-report.json',{},names)
   with self.assertRaisesRegex(action.Held,'repair-fixed-output'):action.emit(out,'arbitrary.json',{},())
   (out/'execution-originals.json').write_bytes(b'{}');(out/'execution-originals.json').chmod(0o600)
   ref=action.emit(out,'terminal-report.json',{'fixed':'phase'},('execution-originals.json',));self.assertEqual(Path(ref['path']).read_bytes(),action.encoded({'fixed':'phase'}))
   with self.assertRaisesRegex(action.Held,'repair-output-original-census'):action.emit(out,'terminal-report.json',{},('execution-originals.json',))
if __name__=='__main__':unittest.main()
