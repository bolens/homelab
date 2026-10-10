"""Real private FD/read/kernel closure; explicit selected-process/producer fixtures.

No Docker, real selected image, or serialized capability acceptance is asserted.
"""
import copy
import hashlib
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_reader_lifecycle_parent as old
import comic_archive_terminal_vectors as vectors
p=old.p

class Tests(unittest.TestCase):
 setUp=old.Tests.setUp
 def setup(self):
  x=self.parent;out=x.op/'execute';out.mkdir(mode=0o700);p._OUTPUT_NODES[x]={str(out):tuple(p.five(out.lstat()))}
  x.plan.update(version=11,action='archive-one',terminal_mode='same-child-v1');x.plan['mounts'][0]['child']=str(self.root);x.plan['mounts'][1]['child']=str(x.op);x.mapping=p.Paths(x.plan['mounts'])
  owner={'table':'issues','issueid':'123','parentcomicid':'456','releasecomicid':'456'};operation='d'*64
  request=old.fixture_ref(self.root/'request.json',p.encode(dict(version=1,owner=owner,operation_id=operation)));x.plan['producer_inputs']={'archive_request':request}
  x.plan['sdk_map']=old.fixture_ref(self.root/'sdk-map.json',p.encode({'publication_api.py':'a'*64}))
  stage=self.root/'stage';stage.mkdir(mode=0o700);meta=old.fixture_ref(stage/'preparation.json',b'{}');baseline=old.fixture_ref(self.root/'baseline.json',b'{}')
  false=dict(mutation_authority=False,publication_acceptance=False,ordinary_import_grant=False,reader_index_acceptance=False,automatic_replay=False)
  eh=old.fixture_ref(self.root/'execute-history.json',p.encode(dict(owner=owner,operation_id=operation,**false)))
  th=old.fixture_ref(self.root/'terminal-history.json',p.encode(dict(owner=owner,operation_id=operation,**false)))
  native={'config_module':dict(path='/app/mylar3/mylar/config.py',sha256='a'*64,signature9=[1,2,3,4,5,0o100644,1000,1000,1]),'main_module':dict(path='/app/mylar3/Mylar.py',sha256='b'*64,signature9=[1,3,3,4,5,0o100644,1000,1000,1])}
  scope=old.fixture_ref(x.op/'execute-input.native-scope.json',p.encode(native));x.generated[scope['path']]=scope;p._GENERATED[x]=p.encode(x.generated)
  original=dict(version=1,kind='archive-one-original-custody',owner=owner,operation_id=operation,baseline=baseline,preparation=meta,preparation_directory9=p.nine(stage.lstat()),reader={'fixture_only':True},publication_acceptance=False,mutation_authority=False)
  orig=old.fixture_ref(out/'execution-originals.json',p.encode(original))
  self.absent=self.root/'missing.cbz';self.claim=self.root/'claimed.cbz';self.claim.write_bytes(b'original')
  facts=[baseline,meta,eh,th];v=dict(files=[[r['path'],r['signature9']] for r in facts]+[[str(stage),p.nine(stage.lstat())]],nodes=[],claims=[[str(self.absent),None],[str(self.claim),[self.claim.stat().st_dev,self.claim.stat().st_ino,self.claim.stat().st_mode,self.claim.stat().st_uid,self.claim.stat().st_gid,1]]],censuses=[[str(out),['execute-report.json','execution-originals.json','terminal-report.json']]],absent=[str(self.root/'writer.pending')])
  summary=dict(kind='fresh-repair-terminal-observation',operation_id=operation,owner=owner,baseline_sha256=baseline['sha256'],reader_reference_preservation=True,native_only_size_cell_transition=True,publication_acceptance=False,ordinary_import_grant=False)
  common=dict(version=1,outcome='observed-forward',owner=owner,operation_id=operation,originals=orig,baseline=baseline,execute_history=eh,phase='execute',nonce=x.plan['nonce'],final_ack_required=True,provider_continuity_verified=False,**false)
  terminal=dict(common,kind='archive-one-independent-terminal-observation',independent_observation=summary,history=th,original_vectors=v);tr=old.fixture_ref(out/'terminal-report.json',p.encode(terminal))
  execute=dict(common,kind='archive-one-owning-execute-observation',terminal_report=tr);er=old.fixture_ref(out/'execute-report.json',p.encode(execute))
  self.refs=dict(originals=orig,terminal_report=tr,execution_report=er);self.original=orig;self.terminal=tr
  self.message=dict(protocol='reader-lifecycle-pipe-v1',type='terminal-observation',nonce=x.plan['nonce'],input_sha256=self.proof['sha256'],parent_sha256=self.source['sha256'],sequence=4,challenge='e'*64,terminal=copy.deepcopy(self.refs))
  self.current=dict(Id='4'*64,Image=x.plan['selected_image'],Name='fixture',Path='/init',Args=[],Config={},HostConfig={},Mounts=[],NetworkSettings={},State=dict(Running=True,Status='running',Pid=123,StartedAt='start',FinishedAt='',ExitCode=0,Error='',Paused=False,Restarting=False,OOMKilled=False,Dead=False))
  x.continuous=lambda:{};x.inspect=lambda _:copy.deepcopy(self.current);x.observer=vectors
  p._PHASES[x]={'execute':{'accepted':True}};p._CORES[x]=x.core
  x.files={self.source['path']:tuple(self.source['signature9'])};x.nodes={}
  self.parent=x
 def go(self):return self.parent.accept_archive_terminal(self.proof,[],self.message,self.current,copy.deepcopy(self.current),p.encode(self.message))
 def test_original_selected_child_fixed_reports_factual_release(self):
  self.setup();answer=p.decode(self.go());self.assertEqual(answer['type'],'terminal-release');self.assertTrue(all(v is False for v in answer['rights'].values()))
  r=p._ARCHIVE_TERMINAL_ROUNDS[self.parent];self.assertEqual(r['request_sha256'],hashlib.sha256(p.encode(self.message)+b'\n').hexdigest());self.assertEqual(r['response_sha256'],hashlib.sha256(p.encode(answer)+b'\n').hexdigest())
  with self.assertRaises(p.Held):self.go()
 def test_late_original_source_last_inspect_holds(self):
  self.setup();self.parent.inspect=lambda _: (Path(self.source['path']).chmod(0o640) or copy.deepcopy(self.current))
  with self.assertRaises(p.Held):self.go()
 def test_late_original_report_last_inspect_holds(self):
  self.setup();self.parent.inspect=lambda _: (Path(self.terminal['path']).chmod(0o640) or copy.deepcopy(self.current))
  with self.assertRaises(p.Held):self.go()
 def test_late_claim_after_partition_holds(self):
  self.setup();self.parent.inspect=lambda _: (self.absent.write_bytes(b'foreign') and copy.deepcopy(self.current))
  with self.assertRaises(p.Held):self.go()
 def test_restarted_original_producer_holds(self):
  self.setup();self.parent.inspect=lambda _:dict(self.current,State=dict(self.current['State'],Pid=124))
  with self.assertRaises(p.Held):self.go()
 def test_wrong_baseline_joins_hold(self):
  self.setup();p1=Path(self.terminal['path']);doc=p.decode(p1.read_bytes());doc['independent_observation']['baseline_sha256']='0'*64;new=old.fixture_ref(p1,p.encode(doc));self.message['terminal']['terminal_report']=new
  # Execute must reference that same actual new terminal ref before testing the join.
  ep=Path(self.refs['execution_report']['path']);doc=p.decode(ep.read_bytes());doc['terminal_report']=new;self.message['terminal']['execution_report']=old.fixture_ref(ep,p.encode(doc))
  with self.assertRaises(p.Held):self.go()
 def test_default_legacy_and_unborn_holds(self):
  self.setup();self.parent.plan['version']=10
  with self.assertRaises(p.Held):self.go()
  self.parent.plan['version']=11;p._PHASES[self.parent]['execute']['accepted']=False
  with self.assertRaises(p.Held):self.go()
 def test_raw_request_not_reconstructed(self):
  self.setup()
  with self.assertRaises(p.Held):self.parent.accept_archive_terminal(self.proof,[],self.message,self.current,self.current,b' '+p.encode(self.message))
 def test_last_helper_parent_logical_mutation_holds(self):
  self.setup();real=self.parent.close_archive_terminal_round
  def late(record):real(record);self.parent.plan['terminal_mode']='foreign'
  self.parent.close_archive_terminal_round=late
  with self.assertRaises(p.Held):self.go()
 def test_last_claim_mutates_earlier_report_holds(self):
  self.setup();real=p.os.lstat;fired=[]
  def late(path,*a,**kw):
   z=real(path,*a,**kw)
   if Path(path)==self.claim and p._ARCHIVE_TERMINAL_ROUNDS.get(self.parent) is not None and not fired:Path(self.terminal['path']).chmod(0o640);fired.append(True)
   return z
  with patch.object(p.os,'lstat',late),self.assertRaises(p.Held):self.go()
  self.assertTrue(fired)

 def test_first_partition_parent_original_never_rebases(self):
  self.setup();real=self.parent.observer.partition
  def late(*args,**kwargs):
   result=real(*args,**kwargs);self.parent.plan['terminal_mode']='foreign';return result
  with patch.object(self.parent.observer,'partition',late),self.assertRaises(p.Held):self.go()
 def test_final_round_record_mutation_holds(self):
  self.setup();real=self.parent.close_archive_terminal_round
  def late(record):real(record);record['challenge']='0'*64
  self.parent.close_archive_terminal_round=late
  with self.assertRaises(p.Held):self.go()

 def test_real_OS_stdio_terminal_dialogue_exact_encoded_bytes(self):
  self.setup();message=copy.deepcopy(self.message)
  ack={'nonce':message['nonce'],'phase':'execute','source_sha256':self.provider['sha256'],'report':self.refs['execution_report'],'publication_acceptance':False,'reader_resume_authority':False}
  script="import sys,json;message=json.loads(sys.argv[1]);sys.stdout.write(json.dumps(message,sort_keys=True,separators=(',',':'))+'\\n');sys.stdout.flush();reply=sys.stdin.buffer.readline();value=json.loads(reply);assert value['type']=='terminal-release';ack=json.loads(sys.argv[2]);sys.stdout.write(json.dumps({'type':'ACK','ack':ack},sort_keys=True,separators=(',',':'))+'\\n');sys.stdout.flush()"
  real=subprocess.Popen
  def spawn(*args,**kwargs):return real([sys.executable,'-I','-B','-c',script,p.encode(message).decode(),p.encode(ack).decode()],**kwargs)
  def handler(value,raw=None):
   if value is None:return None
   return self.parent.accept_archive_terminal(self.proof,[],value,self.current,self.current,raw)
  with patch.object(p.subprocess,'Popen',spawn):answer=p.ScopedDocker().interactive('4'*64,handler,5)
  self.assertEqual(answer,ack);self.assertIn(self.parent,p._ARCHIVE_TERMINAL_ROUNDS)

if __name__=='__main__':unittest.main()
