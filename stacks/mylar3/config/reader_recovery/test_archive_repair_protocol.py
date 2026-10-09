"""Source protocol and real disposable fixture flows; no installed authority."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import comic_archive_repair_action as a
import comic_archive_repair_protocol as p
OWNER={'table':'issues','issueid':'123','parentcomicid':'456','releasecomicid':'456'}
REQUEST={'version':1,'owner':OWNER,'operation_id':'a'*64}
class Protocol(unittest.TestCase):
 def inputs(self):
  ref={'path':'/private/control.json','sha256':'b'*64};controls={name:copy.deepcopy(ref) for name in a.ROLES}
  return dict(phase='execute',request=copy.deepcopy(REQUEST),controls=controls,archive_scopes=ref,operation='/private/execute',sdk_map=ref,nonce='c'*64,parent_sha256='d'*64,selected_image='sha256:'+'e'*64,provider={'path':str(HERE/'comic_archive_repair_action.py'),'sha256':'f'*64},input_path='/private/execute-input.json')
 def test_actual_command_no_self_hash(self):
  values=self.inputs();out=p.phase_input(**values);plan=json.loads(out['input_bytes']);args=types.SimpleNamespace(phase='execute',input=values['input_path'],input_sha256=out['input_sha256'],source_sha256=values['provider']['sha256'])
  self.assertEqual(a.validate_plan(plan,args,out['actual_command']),plan);self.assertFalse(out['custody_produced']);self.assertFalse(out['mutation_authority'])
 def test_five_roles_not_accepted(self):
  v=self.inputs();v['controls']['timestamp_evidence']=v['sdk_map']
  with self.assertRaises(a.Held):p.phase_input(**v)
 def test_path_witness_and_grant_not_user_request(self):
  for name,value in [('source','/archive.cbz'),('url','file:///comic'),('witness',{}),('mutation_authority',True),('retention_root','/private')]:
   v=copy.deepcopy(REQUEST);v[name]=value
   with self.assertRaises(a.Held):a.owner_request(v)
 def test_type_sensitive_version(self):
  for version in (True,1.0,'1'):
   v=copy.deepcopy(REQUEST);v['version']=version
   with self.assertRaises(a.Held):a.owner_request(v)
 def test_owner_issue_parent_mismatch(self):
  v=copy.deepcopy(REQUEST);v['owner']['releasecomicid']='789'
  with self.assertRaises(a.Held):a.owner_request(v)
 def test_owner_alias_or_unknown_table(self):
  for key,value in [('table','unknown'),('issueid',True),('issueid','../123')]:
   v=copy.deepcopy(REQUEST);v['owner'][key]=value
   with self.assertRaises(a.Held):a.owner_request(v)
 def test_operation_id_never_automatically_replaced(self):
  v=self.inputs();out=p.phase_input(**v);self.assertEqual(json.loads(out['input_bytes'])['operation_id'],REQUEST['operation_id'])
  v['request']['operation_id']='../retry'
  with self.assertRaises(a.Held):p.phase_input(**v)
 def test_duplicate_command_flag_refused(self):
  v=self.inputs();out=p.phase_input(**v);plan=json.loads(out['input_bytes']);args=types.SimpleNamespace(phase='execute',input=v['input_path'],input_sha256=out['input_sha256'],source_sha256=v['provider']['sha256'])
  with self.assertRaises(a.Held):a.validate_plan(plan,args,out['actual_command']+['--input',v['input_path']])
 def test_preparation_boolean_not_a_plan_grant(self):
  v=self.inputs();out=p.phase_input(**v);plan=json.loads(out['input_bytes']);plan['preparation']=True;args=types.SimpleNamespace(phase='execute',input=v['input_path'],input_sha256=out['input_sha256'],source_sha256=v['provider']['sha256'])
  with self.assertRaises(a.Held):a.validate_plan(plan,args,out['actual_command'])
 def test_verify_requires_original_full9_reference(self):
  v=self.inputs();v['phase']='verify-terminal'
  with self.assertRaises(a.Held):p.phase_input(**v)
  v['execution_originals']={'path':'/private/execute/execution-originals.json','sha256':'a'*64,'signature9':[1]*9};out=p.phase_input(**v);self.assertEqual(json.loads(out['input_bytes'])['execution_originals'],v['execution_originals'])
 def test_execute_rejects_foreign_terminal_evidence(self):
  v=self.inputs();v['execution_originals']={'path':'/private','sha256':'a'*64,'signature9':[1]*9}
  with self.assertRaises(a.Held):p.phase_input(**v)
 def test_neutral_roles_no_timestamp_or_five_plan(self):
  self.assertEqual(len(a.ROLES),8);self.assertNotIn('reviewed_plan',a.ROLES);self.assertNotIn('timestamp_evidence',a.ROLES)
 def test_original_execution_type_aliases_and_unknown_keys(self):
  ref={'path':'/private/original','signature9':[1]*9,'sha256':'a'*64}
  v={'version':1,'kind':'archive-one-original-custody','owner':OWNER,'operation_id':REQUEST['operation_id'],'baseline':ref,'preparation':ref,'preparation_directory9':[1]*9,'reader':{},'publication_acceptance':False,'mutation_authority':False}
  self.assertEqual(a.original_execution(v,REQUEST),v)
  for key,value in [('version',True),('version',1.0),('mutation_authority',0),('publication_acceptance',0),('unknown',True),('operation_id','b'*64)]:
   changed=copy.deepcopy(v);changed[key]=value
   with self.assertRaises(a.Held):a.original_execution(changed,REQUEST)
 def test_original_execution_signature_alias_held(self):
  ref={'path':'/private/original','signature9':[1]*9,'sha256':'a'*64};ref['signature9'][0]=True
  v={'version':1,'kind':'archive-one-original-custody','owner':OWNER,'operation_id':REQUEST['operation_id'],'baseline':ref,'preparation':ref,'preparation_directory9':[1]*9,'reader':{},'publication_acceptance':False,'mutation_authority':False}
  with self.assertRaises(a.Held):a.original_execution(v,REQUEST)
 def test_sdk_map_normal_names(self):
  self.assertEqual(a.sdk_map({'publication_api.py':'a'*64}),{'publication_api.py':'a'*64})
  for name in ('publication_api.py.tmp','../publication_api.py','Publication_api.py'):
   with self.assertRaises(a.Held):a.sdk_map({name:'a'*64})
 def test_exact_type_receipts_refused(self):
  for obj in ({'stopped':True},True,object()):
   modules={'publication_reader_lifecycle':types.SimpleNamespace(StoppedReaderCustody=type('ActualCustody',(),{})),'publication_native_configured_scope':types.SimpleNamespace(NativeConfiguredScope=type('ActualScope',(),{}))}
   with patch.object(a,'installed'),self.assertRaises(a.Held):a.exact_pair(modules,obj,obj)
 def test_wrong_installed_origin(self):
  with self.assertRaises(a.Held):a.installed({'publication_api':types.SimpleNamespace(__file__='/tmp/fake/publication_api.py')})
 def test_terminal_vector_factory_missing_before_write(self):
  with self.assertRaises(a.Held):a.require_terminal_observers({'publication_archive_verifier':types.SimpleNamespace()})
 def test_parent_pin_remains_unset(self):self.assertIsNone(a.PARENT_SOURCE_SHA)
 def test_emit_intended_bytes_and_private_mode(self):
  with tempfile.TemporaryDirectory() as t:
   r=a.emit(Path(t),'execution-originals.json',{'facts':'opaque'},());self.assertEqual(json.loads(Path(r['path']).read_bytes()),{'facts':'opaque'});self.assertEqual(Path(r['path']).stat().st_mode&0o777,0o600)
 def test_emit_replay_or_foreign_child_held(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'foreign').write_bytes(b'keep')
   with self.assertRaises(a.Held):a.emit(root,'execution-originals.json',{},())
   self.assertEqual((root/'foreign').read_bytes(),b'keep')
 def test_first_output_corruption_held(self):
  with tempfile.TemporaryDirectory() as t:
   real=a.write
   def late(*args,**kw):r=real(*args,**kw);Path(r['path']).write_bytes(b'{}');return r
   with patch.object(a,'write',side_effect=late),self.assertRaises(a.Held):a.emit(Path(t),'execution-originals.json',{'intended':True},())
 def test_last_output_checked_callback_foreign_child_held(self):
  with tempfile.TemporaryDirectory() as t:
   real=a.checked
   def late(*args,**kw):r=real(*args,**kw);(Path(t)/'foreign').write_bytes(b'keep');return r
   with patch.object(a,'checked',side_effect=late),self.assertRaises(a.Held):a.emit(Path(t),'execution-originals.json',{},())
 def test_sealed_observation_missing_claim(self):
  with tempfile.TemporaryDirectory() as t:
   pth=Path(t)/'missing';v=a.seal_vectors({}, {}, (), {pth:None}, {});pth.write_bytes(b'foreign')
   with self.assertRaises(a.Held):a.close_vectors(v)
 def test_final_claim_directory_helper_not_called(self):
  with tempfile.TemporaryDirectory() as t:
   path=Path(t)/'original';path.write_bytes(b'original');z=path.stat();v=a.seal_vectors({}, {}, (), {path:(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)}, {})
   def late(mode):path.chmod(0o640);raise AssertionError('final semantic helper must never run')
   with patch.object(a.stat,'S_ISDIR',side_effect=late):a.close_vectors(v)
   self.assertEqual(path.stat().st_mode&0o777,0o644)
 def test_sealed_observation_file_incarnation(self):
  with tempfile.TemporaryDirectory() as t:
   pth=Path(t)/'file';pth.write_bytes(b'original');v=a.seal_vectors({pth:a.nine(pth.stat())},{},(),{},{});q=pth.with_name('replacement');q.write_bytes(b'original');os.replace(q,pth)
   with self.assertRaises(a.Held):a.close_vectors(v)
 def test_sealed_observation_companion_absence(self):
  with tempfile.TemporaryDirectory() as t:
   pth=Path(t)/'database-wal';v=a.seal_vectors({}, {}, (pth,), {}, {});pth.write_bytes(b'foreign')
   with self.assertRaises(a.Held):a.close_vectors(v)
 def test_no_synthetic_five_imports(self):
  source=(HERE/'comic_archive_repair_action.py').read_text();self.assertNotIn("'publication_reader_admission'",source);self.assertNotIn("'publication_negative_batch'",source)
if __name__=='__main__':unittest.main()
