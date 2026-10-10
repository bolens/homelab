"""Real neutral backup/SQLite/pins; exact finite version-pair fixtures."""
import hashlib
import json
from pathlib import Path
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_archive_proof_producer as fixture
p=fixture.p;a=fixture.a

class Tests(unittest.TestCase):
 setUp=fixture.Controls.setUp
 go=fixture.Controls.go
 phase=fixture.Controls.phase
 def paired(self,plan_version=11,input_version=2,mode='same-child-v1',extra=False):
  request=self.phase();pp=Path(self.plan['path']);plan=json.loads(pp.read_bytes());plan['version']=plan_version
  if plan_version in (11,12):plan['terminal_mode']='same-child-v1'
  if plan_version==12:
   source=a.write(self.root/'worker-source-fixture.json',{'fixture':'original-host-source-ref-shape-only'});sources=a.write(self.root/'worker-source-map-fixture.json',{'fixture':'source-preflight-parent-owned'})
   plan['worker_observation']={'mode':'original-pipes-v1','source':source,'image_sources':sources}
  if plan_version not in (11,12):plan.pop('terminal_mode',None)
  raw=a.encoded(plan);pp.write_bytes(raw);self.plan.update(sha256=hashlib.sha256(raw).hexdigest(),signature9=a.nine(pp.lstat()));request['parent_plan']=dict(self.plan)
  inv=request['context']['invocation'];ip=Path(inv['input_path']);doc=json.loads(ip.read_bytes());doc['version']=input_version
  if mode is not None:doc['terminal_mode']=mode
  if extra:doc['extra']='foreign'
  raw=a.encoded(doc);ip.write_bytes(raw);inv['input_sha256']=hashlib.sha256(raw).hexdigest();inv['command'][9]=inv['input_sha256']
  return request
 def test_exact_plan11_input2_same_child_preserves_eight_roles(self):
  request=self.paired();answer=p.produce('phase-custody',request,watch=self.parent.continuous)['evidence'];self.assertEqual(set(answer),{'reader','proofs','birth_seed'});self.assertEqual(answer['proofs']['archive_sdk_map'],self.sdkmap)
 def test_plan10_input2_held(self):
  with self.assertRaises(p.Held):p.produce('phase-custody',self.paired(10,2),watch=self.parent.continuous)
 def test_plan11_input1_held(self):
  with self.assertRaises(p.Held):p.produce('phase-custody',self.paired(11,1),watch=self.parent.continuous)
 def test_missing_same_child_mode_held(self):
  with self.assertRaises(p.Held):p.produce('phase-custody',self.paired(mode=None),watch=self.parent.continuous)
 def test_unknown_same_child_mode_held(self):
  with self.assertRaises(p.Held):p.produce('phase-custody',self.paired(mode='foreign'),watch=self.parent.continuous)
 def test_extra_input_key_held(self):
  with self.assertRaises(p.Held):p.produce('phase-custody',self.paired(extra=True),watch=self.parent.continuous)

 def test_exact_plan12_input2_same_child_eight_roles(self):
  answer=p.produce('phase-custody',self.paired(12,2),watch=self.parent.continuous)['evidence'];self.assertEqual(set(answer),{'reader','proofs','birth_seed'})
 def test_plan12_input1_held(self):
  with self.assertRaises(p.Held):p.produce('phase-custody',self.paired(12,1),watch=self.parent.continuous)
 def test_plan12_unknown_worker_mode_held(self):
  request=self.paired(12,2);path=Path(self.plan['path']);doc=json.loads(path.read_bytes());doc['worker_observation']['mode']='foreign';raw=a.encoded(doc);path.write_bytes(raw);request['parent_plan'].update(sha256=hashlib.sha256(raw).hexdigest(),signature9=a.nine(path.stat()))
  with self.assertRaises(p.Held):p.produce('phase-custody',request,watch=self.parent.continuous)
 def test_plan12_extra_worker_field_held(self):
  request=self.paired(12,2);path=Path(self.plan['path']);doc=json.loads(path.read_bytes());doc['worker_observation']['authority']=True;raw=a.encoded(doc);path.write_bytes(raw);request['parent_plan'].update(sha256=hashlib.sha256(raw).hexdigest(),signature9=a.nine(path.stat()))
  with self.assertRaises(p.Held):p.produce('phase-custody',request,watch=self.parent.continuous)

if __name__=='__main__':unittest.main()
