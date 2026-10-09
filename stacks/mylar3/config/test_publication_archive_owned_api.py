"""Primary publication request routing using real Controller/Writer/catalog.

Host tests substitute SDK module resolution, not authority, catalog or leases.
Installed-image route and primary-key adapter placement remain separate gates.
"""
import inspect
import json
from pathlib import Path
import sys
import unittest
import types
from unittest.mock import patch
import publication_archive_owned as core
import publication_archive_prepare_routes as route
import publication_api as api
# Reuse owning real disposable catalog/bootstrap fixture after module resolution.
import test_publication_archive_owned as fixture
class Controls(unittest.TestCase):
 def setUp(self):
  self.case=fixture.Controls('test_current_owner_prepare_retains_original_and_has_no_authority');self.case.setUp();self.addCleanup(self.case.doCleanups)
  self.case.controller=api.Controller(self.case.root,[self.case.library],tool_root=self.case.modules[2].TOOL_ROOT)
  self.case.modules[0]=api
  p=patch.object(core,'sdk',return_value=self.case.modules);p.start();self.addCleanup(p.stop)
  self.owner=self.case.owner;self.operation_id='2'*64
 def call(self,action='prepare-archive-repair',**fields):
  raw=json.dumps(dict(version=1,action=action,owner=self.owner,operation_id=self.operation_id,**fields))
  return self.case.controller.dispatch(api.request(raw))
 def test_primary_controller_prepare_and_readonly_status(self):
  source=self.case.source.read_bytes();db=self.case.database.read_bytes()
  p=self.call();self.assertEqual(p['outcome'],'prepared');self.assertFalse(p['mutation_authority']);self.assertFalse(p['adoption_authority'])
  op=self.case.root/('archive-repair-'+self.operation_id);before={x.name:core.signature(x) for x in op.iterdir()}
  r=self.call('archive-repair-status');self.assertEqual(r['token'],p['token']);self.assertEqual(r['outcome'],'prepared')
  self.assertEqual({x.name:core.signature(x) for x in op.iterdir()},before);self.assertEqual(self.case.source.read_bytes(),source);self.assertEqual(self.case.database.read_bytes(),db)
 def test_adoption_routes_hold_real_writer_before_dispatch(self):
  calls=[]
  def dispatched(controller,writer,value):
   core.writer_pair(controller,writer,self.case.modules)
   calls.append(value['action'])
   return {'outcome':'queued-review','mutation_authority':False}
  module=types.ModuleType('publication_archive_dispatch');module.dispatch=dispatched
  with patch.dict(sys.modules,{'publication_archive_dispatch':module}):
   for action in ('request-archive-repair-adoption','archive-repair-adoption-status'):
    self.assertFalse(self.call(action)['mutation_authority'])
  self.assertEqual(calls,['request-archive-repair-adoption','archive-repair-adoption-status'])
 def test_no_path_or_witness_fields(self):
  for fields in ({'source':'/foreign'},{'witness':{}},{'observed':[]},{'token':'a'*64},{'reader_preserved':True}):
   with self.assertRaises(ValueError):api.request(json.dumps(dict(version=1,action='prepare-archive-repair',owner=self.owner,operation_id=self.operation_id,**fields)))
 def test_invalid_owner_and_nonce_before_state(self):
  for owner,operation in ((dict(self.owner,issueid='../1'),self.operation_id),(self.owner,True),(self.owner,'../path')):
   with self.assertRaises(ValueError):api.request(json.dumps(dict(version=1,action='prepare-archive-repair',owner=owner,operation_id=operation)))
 def test_duplicate_json_fields_rejected(self):
  with self.assertRaises(ValueError):api.request('{"version":1,"action":"archive-repair-status","owner":{},"operation_id":"'+self.operation_id+'","operation_id":"'+'3'*64+'"}')
 def test_missing_status_no_creation(self):
  before=set(self.case.root.iterdir());self.assertEqual(self.call('archive-repair-status')['outcome'],'missing');self.assertEqual(set(self.case.root.iterdir()),before)
 def test_repeat_prepare_no_replay_or_overwrite(self):
  self.call();op=self.case.root/('archive-repair-'+self.operation_id);before={x.name:core.fact(x,512*1024**2+2,__import__('time').monotonic()+5) for x in op.iterdir()}
  with self.assertRaises(ValueError):self.call()
  self.assertEqual(before,{x.name:core.fact(x,512*1024**2+2,__import__('time').monotonic()+5) for x in op.iterdir()})
 def test_ordinary_writer_flags_not_recovery(self):
  with patch.object(core,'writer_pair',wraps=core.writer_pair) as paired:self.call()
  self.assertTrue(paired.call_args_list)
  self.assertFalse(getattr(self.case.writer.local[1],'allow_pending',False))
 def test_pending_marker_refuses_before_stage(self):
  (self.case.writer.root/'normalizer-v1.pending').write_bytes(b'foreign')
  with self.assertRaises(Exception):self.call()
  self.assertFalse((self.case.root/('archive-repair-'+self.operation_id)).exists())
 def test_lost_response_status_recovers_only_observation(self):
  real=route.summary
  def lost(*a,**kw):
   result=real(*a,**kw)
   if a[0]=='prepare-archive-repair':raise ValueError('fixture-lost-response')
   return result
  with patch.object(route,'summary',side_effect=lost),self.assertRaises(ValueError):self.call()
  self.assertEqual(self.call('archive-repair-status')['outcome'],'prepared')
 def test_partial_copy_failure_has_no_token_or_replay(self):
  with patch.object(core,'preserve',side_effect=ValueError('fixture-copy-fail')),self.assertRaises(ValueError):self.call()
  status=self.call('archive-repair-status');self.assertEqual(status['outcome'],'retained-incomplete');self.assertIsNone(status['token']);self.assertFalse(status['source_preservation_verified'])
  with self.assertRaises(ValueError):self.call()
 def test_changed_source_status_held(self):
  self.call();self.case.source.write_bytes(b'foreign')
  with self.assertRaises(ValueError):self.call('archive-repair-status')
 def test_samebytes_custody_replacement_status_held(self):
  self.call();p=self.case.root/('archive-repair-'+self.operation_id)/'original.arc';raw=p.read_bytes();p.unlink();p.write_bytes(raw)
  with self.assertRaises(ValueError):self.call('archive-repair-status')
 def test_changed_catalog_status_held(self):
  self.call();self.case.sql("UPDATE issues SET Status='Wanted'")
  with self.assertRaises(ValueError):self.call('archive-repair-status')
 def test_custody_metadata_and_pages_status_held(self):
  self.call();p=self.case.root/('archive-repair-'+self.operation_id)/'prepared.cbz';p.write_bytes(p.read_bytes().replace(b'page one',b'bad page'))
  with self.assertRaises(ValueError):self.call('archive-repair-status')
 def test_foreign_stage_child_refused(self):
  self.call();op=self.case.root/('archive-repair-'+self.operation_id);(op/'foreign').write_bytes(b'foreign')
  with self.assertRaises(ValueError):self.call('archive-repair-status')
 def test_unknown_managed_stage_name_refused(self):
  (self.case.root/'archive-repair-foreign').mkdir(mode=0o700)
  with self.assertRaises(ValueError):self.call('archive-repair-status')
 def test_stage_count_bound_before_creation(self):
  for n in range(8):(self.case.root/('archive-repair-'+format(n,'064x'))).mkdir(mode=0o700)
  with self.assertRaises(ValueError):self.call()
  self.assertFalse((self.case.root/('archive-repair-'+self.operation_id)).exists())
 def test_byte_reservation_bound_before_creation(self):
  with patch.object(route,'MAX_STAGE_BYTES',1024),self.assertRaises(ValueError):self.call()
  self.assertFalse((self.case.root/('archive-repair-'+self.operation_id)).exists())
 def test_api_returns_no_paths_or_witness(self):
  result=self.call();text=json.dumps(result);self.assertNotIn(str(self.case.root),text);self.assertNotIn('witness',text);self.assertNotIn('source_sha256',text)
 def test_late_status_read_creates_companion_held(self):
  self.call();real=core.fact;fired=[]
  def late(p,*a):
   result=real(p,*a)
   if Path(p).name=='preparation.json' and not fired:Path(str(self.case.database)+'-wal').write_bytes(b'late');fired.append(True)
   return result
  with patch.object(core,'fact',side_effect=late),self.assertRaises(ValueError):self.call('archive-repair-status')
  self.assertTrue(fired)
 def test_late_prepare_summary_adds_stage_child_held(self):
  real=route.summary
  def late(*a,**kw):
   result=real(*a,**kw);(self.case.root/('archive-repair-'+self.operation_id)/'foreign').write_bytes(b'late');return result
  with patch.object(route,'summary',side_effect=late),self.assertRaises(ValueError):self.call()
 def test_changed_grant_on_disk_never_authority(self):
  self.call();p=self.case.root/('archive-repair-'+self.operation_id)/'preparation.json';body=json.loads(p.read_text());body['mutation_authority']=True
  body['token']=core.digest({k:v for k,v in body.items() if k!='token'});p.write_bytes(core.compact(body))
  with self.assertRaises(ValueError):self.call('archive-repair-status')
 def test_compiled_primary_adapter_auth_contract_unchanged(self):
  # Existing exact primary-key/POST adapter remains the only public entry.
  import patch_publication_guard as adapter
  source=adapter.METHOD
  for phrase in ("self.apikey != key","apitype","cherrypy.request.method != 'POST'","set(kwargs) != {'request'}"):
   self.assertIn(phrase,source)
 def test_routes_have_no_adopt_dispatch(self):
  with self.assertRaises(ValueError):api.request(json.dumps(dict(version=1,action='adopt-archive-repair',owner=self.owner,operation_id=self.operation_id)))

 def test_last_status_namespace_read_companion_not_acknowledged(self):
  self.call();real=route.close;fired=[]
  def late(*a):
   result=real(*a);Path(str(self.case.database)+'-wal').write_bytes(b'late');fired.append(True);return result
  with patch.object(route,'close',side_effect=late),self.assertRaises(ValueError):self.call('archive-repair-status')
  self.assertTrue(fired)
 def test_last_status_namespace_catalog_alias_not_acknowledged(self):
  self.case.sql('INSERT INTO issues VALUES (?,?,?,?)',('777','456','late.cbz','Wanted'));self.call();real=route.close;fired=[]
  def late(*a):
   result=real(*a);(self.case.library/'late.cbz').symlink_to(self.case.source);fired.append(True);return result
  with patch.object(route,'close',side_effect=late),self.assertRaises(ValueError):self.call('archive-repair-status')
  self.assertTrue(fired)
 def test_last_prepare_sdk_changes_old_stage_held(self):
  self.call();old=self.case.root/('archive-repair-'+self.operation_id)/'original.arc';self.operation_id='3'*64
  real=core.RepairPreparation.close_passive;fired=[]
  def late(prep):
   result=real(prep)
   if prep._binding['operation_id']==self.operation_id and not fired:old.write_bytes(b'late');fired.append(True)
   return result
  with patch.object(core.RepairPreparation,'close_passive',new=late),self.assertRaises(ValueError):self.call()
  self.assertTrue(fired)

 def test_status_requested_owner_must_match_intent(self):
  self.call();self.owner=dict(self.owner,issueid='777');self.case.sql('INSERT INTO issues VALUES (?,?,?,?)',('777','456','another.cbz','Downloaded'))
  with self.assertRaises(ValueError):self.call('archive-repair-status')
 def test_late_status_namespace_source_replacement_held(self):
  self.call();real=route.close;fired=[]
  def late(*a):
   result=real(*a);source=self.case.source;raw=source.read_bytes();source.unlink();source.write_bytes(raw);fired.append(True);return result
  with patch.object(route,'close',side_effect=late),self.assertRaises(ValueError):self.call('archive-repair-status')
  self.assertTrue(fired)
 def test_status_stale_census_not_new_preparation(self):
  self.call();marker=self.case.writer.root/'publication-v1.json';before=marker.read_bytes();marker.write_bytes(before+b' ')
  with self.assertRaises(ValueError):self.call('archive-repair-status')
 def test_status_derivative_error_is_bounded(self):
  self.call();path=self.case.root/('archive-repair-'+self.operation_id)/'prepared.cbz';path.write_bytes(b'private/member-secret')
  with self.assertRaisesRegex(ValueError,'^Owned archive preparation requires review$') as held:self.call('archive-repair-status')
  self.assertNotIn('member-secret',str(held.exception))

 def primary_handler(self):
  import patch_publication_guard as adapter
  app=types.ModuleType('mylar');app.CONFIG=types.SimpleNamespace(API_ENABLED=True,API_KEY='p'*32,DESTINATION_DIR=str(self.case.library));app.DATA_DIR=str(self.case.root);app.publication_api=api
  cherry=types.SimpleNamespace(request=types.SimpleNamespace(method='POST'));ns={'mylar':app,'cherrypy':cherry}
  exec('class Handler:\n'+adapter.METHOD,ns);h=ns['Handler']();h.apikey='p'*32;h.apitype='normal'
  h._failureResponse=lambda text:{'error':text};h._successResponse=lambda result:{'result':result}
  return h,app,cherry
 def test_primary_key_adapter_calls_genuine_prepare_route(self):
  h,app,_=self.primary_handler();raw=json.dumps(dict(version=1,action='prepare-archive-repair',owner=self.owner,operation_id=self.operation_id))
  # Only the trusted offline scanner root default changes for this host fixture.
  with patch.dict(sys.modules,{'mylar':app}),patch.object(api.Controller.__init__,'__kwdefaults__',{'tool_root':self.case.modules[2].TOOL_ROOT}):h._publicationControl(request=raw)
  self.assertEqual(h.data['result']['outcome'],'prepared');self.assertFalse(h.data['result']['adoption_authority'])
 def test_secondary_key_denies_before_genuine_prepare_route(self):
  h,app,_=self.primary_handler();h.apikey='s'*32;h.apitype='sse'
  with patch.dict(sys.modules,{'mylar':app}),patch.object(api,'execute',wraps=api.execute) as execute:h._publicationControl(request='untrusted')
  execute.assert_not_called();self.assertIn('error',h.data);self.assertFalse((self.case.root/('archive-repair-'+self.operation_id)).exists())

 def test_last_ordinary_purpose_cannot_create_inactive_catalog_alias(self):
  import inspect
  import os
  self.case.sql('INSERT INTO issues VALUES (?,?,?,?)',('777','456','late.cbz','Wanted'))
  alias=self.case.library/'late.cbz';real=self.case.modules[2].ordinary_purpose;fired=[]
  def late(writer):
   result=real(writer)
   if not fired and any(frame.function=='terminal' for frame in inspect.stack()):
    os.symlink(self.case.source,alias);fired.append(True)
   return result
  with patch.object(self.case.modules[2],'ordinary_purpose',side_effect=late),self.assertRaisesRegex(ValueError,'^Owned archive preparation requires review$'):self.call()
  self.assertTrue(fired);self.assertTrue(alias.is_symlink())

 def test_last_ordinary_purpose_cannot_create_negative_marker(self):
  import inspect
  real=self.case.modules[2].ordinary_purpose;fired=[]
  def late(writer):
   result=real(writer)
   if not fired and any(frame.function=='terminal' for frame in inspect.stack()):
    (writer.root/'negative-retirement-v1.pending').write_bytes(b'fixture');fired.append(True)
   return result
  with patch.object(self.case.modules[2],'ordinary_purpose',side_effect=late),self.assertRaisesRegex(ValueError,'^Owned archive preparation requires review$'):self.call()
  self.assertTrue(fired)

 def test_shared_request_deadline_never_restamped(self):
  real=route.namespace;observed=[]
  def record(c,m,deadline):observed.append(deadline);return real(c,m,deadline)
  with patch.object(route,'namespace',side_effect=record):self.call()
  self.assertGreaterEqual(len(observed),3);self.assertTrue(all(v==observed[0] for v in observed))

 def test_terminal_successor_after_last_semantic_callback_holds(self):
  real=self.case.modules[2].ordinary_purpose;fired=[]
  def late(writer):
   result=real(writer)
   if not fired and any(frame.function=='terminal' for frame in inspect.stack()):
    (writer.root/'negative-retirement-v1.terminal-pending').write_bytes(b'fixture');fired.append(True)
   return result
  with patch.object(self.case.modules[2],'ordinary_purpose',side_effect=late),self.assertRaisesRegex(ValueError,'^Owned archive preparation requires review$'):self.call()
  self.assertTrue(fired)

 def test_repair_hold_after_last_route_callback_refuses_status(self):
  self.call()
  for name in ('archive-repair-v1.pending','archive-repair-v1.terminal-pending'):
   with self.subTest(name=name):
    real=self.case.modules[2].ordinary_purpose;fired=[];marker=self.case.writer.root/name
    def late(writer):
     result=real(writer)
     if not fired and any(frame.function=='terminal' for frame in inspect.stack()):
      marker.write_bytes(b'pending');fired.append(True)
     return result
    with patch.object(self.case.modules[2],'ordinary_purpose',side_effect=late),self.assertRaisesRegex(ValueError,'^Owned archive preparation requires review$'):self.call('archive-repair-status')
    self.assertTrue(fired);marker.unlink()

if __name__=='__main__':unittest.main()
