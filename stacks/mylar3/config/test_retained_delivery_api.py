"""Actual public retained factories and actual current API method bodies.
HTTP transport/config objects and upstream API imports are isolated adapters;
installed whole-app/hook/cross-container acceptance is a separate required gate.
"""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch
import test_retained_native_operation as actual
import test_publication_retained_finalize as fixture
import patch_retained_delivery_api as installer

ROOT=Path(__file__).parent
API_SHA='0fade189a300b8c26ea083355d4c13a464c7960a47c6b81a4a66f76f307c83a7'

class Endpoint(unittest.TestCase):
 def setUp(self):
  self.base=actual.Controls('runTest');self.base.setUp();self.addCleanup(self.base.doCleanups)
  self.c=self.base.c;self.n=self.base.n;self.pkg=sys.modules['mylar'];self.pkg.CONFIG.API_ENABLED=True;self.pkg.CONFIG.API_KEY='x'*32
  self.http=SimpleNamespace(request=SimpleNamespace(method='POST'),response=SimpleNamespace(headers={}))
  ctx=patch.dict(sys.modules,{'cherrypy':self.http});ctx.start();self.addCleanup(ctx.stop)
  physical=ROOT/'api.py';before=physical.read_bytes()
  source=(ROOT.parent/'preimages/api.py').read_text()
  self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),API_SHA)
  source=installer.patched_source(source);physical.write_text(source)
  self.addCleanup(physical.write_bytes,before)
  tree=ast.parse(source);node=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Api')
  keep={'_successResponse','_failureResponse','fetchData','_retainedDeliveryFinalize','_retainedDeliveryStatus'}
  node.body=[x for x in node.body if isinstance(x,ast.FunctionDef) and x.name in keep]
  module=ModuleType('mylar.api');module.__file__=str(physical)
  module.__dict__.update(mylar=self.pkg,cherrypy=self.http,json=json,native_writers=self.n,API_ERROR_CODE_DEFAULT=0,
                         logger=SimpleNamespace(fdebug=lambda value:None))
  ctx=patch.dict(sys.modules,{'mylar.api':module});ctx.start();self.addCleanup(ctx.stop)
  ctx=patch.object(self.pkg,'api',module,create=True);ctx.start();self.addCleanup(ctx.stop)
  exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(physical),'exec'),module.__dict__)
  self.api=module
  spec=importlib.util.spec_from_file_location('mylar.publication_retained_api',ROOT/'publication_retained_api.py');self.endpoint=importlib.util.module_from_spec(spec)
  ctx=patch.dict(sys.modules,{spec.name:self.endpoint});ctx.start();self.addCleanup(ctx.stop);spec.loader.exec_module(self.endpoint)
  ctx=patch.object(self.pkg,'publication_retained_api',self.endpoint,create=True);ctx.start();self.addCleanup(ctx.stop)
  self.endpoint.ENABLED=True
  self.handler=object.__new__(module.Api)
  self.handler.__dict__.update(cmd='retainedDeliveryFinalize',apikey='x'*32,apitype='normal',headers='application/json',
                              kwargs={'request':self.base.raw()},img=None,file=None,comicrn=False,data='OK')
 def call(self,command='retainedDeliveryFinalize',raw=None):
  self.handler.cmd=command;self.handler.kwargs={'request':raw if raw is not None else self.base.raw()};self.handler.data='OK'
  return json.loads(self.handler.fetchData())
 def test_current_actual_installer_idempotence(self):
  raw=(ROOT.parent/'preimages/api.py').read_text();patched=installer.patched_source(raw)
  self.assertEqual(installer.patched_source(patched),patched)
  with self.assertRaises(ValueError):installer.patched_source(patched.replace('Exact finite API response','invalid') if 'Exact finite API response' in patched else patched.replace("kwargs.get('request')","kwargs.get('x')",1))
 def test_genuine_api_finalize_and_original_same_daemon_status(self):
  source=self.c.case.original.read_bytes();target=self.c.case.target.read_bytes()
  answer=self.call();self.assertTrue(answer['success']);self.assertEqual(answer['data']['outcome'],'fresh-retained-backend-finalized')
  self.assertEqual(self.call('retainedDeliveryStatus'),answer)
  self.assertFalse(answer['data']['ordinary_import_grant']);self.assertFalse(answer['data']['cleanup_grant'])
  self.assertEqual(self.c.case.original.read_bytes(),source);self.assertEqual(self.c.case.target.read_bytes(),target)
 def test_auth_default_method_and_callback_refuse_before_producer(self):
  for field,value in [('apikey','y'*32),('apitype','secondary')]:
   with patch.object(self.handler,field,value):self.assertFalse(self.call()['success'])
  for field,value in [('API_ENABLED',False),('API_KEY','short')]:
   with patch.object(self.pkg.CONFIG,field,value):self.assertFalse(self.call()['success'])
  with patch.object(self.endpoint,'ENABLED',False):self.assertFalse(self.call()['success'])
  with patch.object(self.http.request,'method','GET'):self.assertFalse(self.call()['success'])
  self.handler.kwargs={'request':self.base.raw(),'callback':'foreign'};self.handler.data='OK'
  self.handler._retainedDeliveryFinalize(**self.handler.kwargs);self.assertFalse(json.loads(self.handler.data)['success'])
  self.assertFalse((self.c.c.root/fixture.r.NAME).exists())
 def test_inherited_recovery_purpose_is_never_narrowed(self):
  with self.n.operation():self.assertFalse(self.call()['success'])
  self.assertFalse((self.c.c.root/fixture.r.NAME).exists())
 def test_changed_source_envelope_target_and_exit_admission_hold(self):
  real=self.api.Api._successResponse
  def serializer(handler,result):
   raw=real(handler,result);self.c.case.target.chmod(0o640);return raw
  with patch.object(self.api.Api,'_successResponse',serializer):self.assertFalse(self.call()['success'])
 def test_extra_envelope_cannot_become_original(self):
  real=self.api.Api._successResponse
  def serializer(handler,result):
   value=json.loads(real(handler,result));value['extra']=True;return json.dumps(value)
  with patch.object(self.api.Api,'_successResponse',serializer):self.assertFalse(self.call()['success'])
 def test_late_exit_admission_target_change_is_held(self):
  real=self.n.admission;calls=[]
  def late(writer,**kwargs):
   answer=real(writer,**kwargs);calls.append(True)
   if len(calls)==2:self.c.case.target.chmod(0o640)
   return answer
  with patch.object(self.n,'admission',late):self.assertFalse(self.call()['success'])
  self.assertEqual(len(calls),2)
 def test_release_callback_change_is_caught_by_passive_original_finish(self):
  cls=fixture.fixture.writers.Writer;real=cls.hold
  from contextlib import contextmanager
  fired=[]
  @contextmanager
  def late(writer,**kwargs):
   with real(writer,**kwargs):yield writer
   if not getattr(writer.local[1],'depth',0) and not fired:
    self.c.case.target.chmod(0o640);fired.append(True)
  with patch.object(cls,'hold',late):self.assertFalse(self.call()['success'])
  self.assertTrue(fired)
 def test_saved_response_receipt_constructor_and_repeat_refuse(self):
  answer=self.call();self.assertTrue(answer['success'])
  with self.assertRaises(fixture.o.Held):fixture.f.RetainedFinalization(answer['data'])
  self.assertFalse(self.call()['success'])
 def test_sameprocess_registry_missing_is_not_hydrated_from_saved_sql(self):
  answer=self.call();key=(str(self.c.c.root),answer['data']['token']);old=fixture.f._FINALS.pop(key)
  try:self.assertFalse(self.call('retainedDeliveryStatus')['success'])
  finally:fixture.f._FINALS[key]=old
 def test_wrong_bool_duplicate_and_oversize_requests_held(self):
  value=dict(self.c.body,version=True)
  for raw in (json.dumps(value),self.base.raw().replace('{','{"version":1,',1),'x'*4096):
   self.assertFalse(self.call(raw=raw)['success'])
 def test_fake_handler_never_gets_self_admission(self):
  fake=SimpleNamespace(cmd='retainedDeliveryFinalize');self.assertFalse(self.n.self_admitted_api(fake))
 def test_genuine_annual_exact_release_and_preservation(self):
  with sqlite3.connect(self.c.c.native_database) as db:
   db.execute('DELETE FROM issues');db.execute('INSERT INTO annuals VALUES(?,?,?,?,?,?)',('123','456','789',self.c.case.target.name,'Archived',0))
  self.c.body['owner']={'table':'annuals','issueid':'123','parentcomicid':'456','releasecomicid':'789'}
  pack=self.c.store.get('pack',self.c.body['pack_id']);pack['members'][0].update(kind='annual',releasecomicid='789');self.c.store.set('pack',self.c.body['pack_id'],pack)
  self.assertTrue(self.call()['success'])
  with sqlite3.connect(self.c.c.native_database) as db:self.assertEqual(db.execute('SELECT ReleaseComicID,Status FROM annuals').fetchall(),[('789','Archived')])
  wrong=dict(self.c.body,owner=dict(self.c.body['owner'],releasecomicid='790'))
  self.assertFalse(self.call('retainedDeliveryStatus',json.dumps(wrong))['success'])

 def test_actual_unknown_sqlite_commit_response_has_no_status_or_retry(self):
  fired=[]
  def fault(frame,event,arg):
   if not fired and event=='c_return' and frame.f_code is fixture.f.finalize.__code__ and getattr(arg,'__name__',None)=='commit' and isinstance(getattr(arg,'__self__',None),sqlite3.Connection):
    fired.append(True);raise OSError('actual commit returned, witness unpublished')
  sys.setprofile(fault)
  try:self.assertFalse(self.call()['success'])
  finally:sys.setprofile(None)
  self.assertTrue(fired)
  with sqlite3.connect(self.c.c.database) as db:self.assertEqual(db.execute('SELECT count(*) FROM records WHERE kind=?',(fixture.f.RECORD_KIND,)).fetchone()[0],1)
  before=self.c.c.database.read_bytes()
  self.assertFalse(self.call('retainedDeliveryStatus')['success']);self.assertFalse(self.call()['success'])
  self.assertEqual(self.c.c.database.read_bytes(),before)
 def test_actual_lost_reply_after_closed_envelope_reconciles_same_daemon(self):
  fired=[]
  def fault(frame,event,arg):
   if not fired and event=='return' and frame.f_code is fixture.f._finish_response.__code__:
    fired.append(True);raise OSError('actual closed envelope reply lost')
  sys.setprofile(fault)
  try:self.assertFalse(self.call()['success'])
  finally:sys.setprofile(None)
  self.assertTrue(fired);before=self.c.c.database.read_bytes()
  self.assertTrue(self.call('retainedDeliveryStatus')['success']);self.assertEqual(self.c.c.database.read_bytes(),before)
 def test_actual_fork_and_missing_original_registry_status_are_held(self):
  self.assertTrue(self.call()['success']);pid=os.fork()
  if pid==0:
   try:result=self.call('retainedDeliveryStatus')
   except BaseException:os._exit(2)
   os._exit(0 if result['success'] is False else 1)
  _,status=os.waitpid(pid,0);self.assertEqual(os.waitstatus_to_exitcode(status),0)
 def test_late_missing_catalog_claim_created_by_serializer_is_held(self):
  folder=self.c.case.case.library/'other';folder.mkdir();missing=folder/'missing.cbz'
  with sqlite3.connect(self.c.c.native_database) as db:db.execute('INSERT INTO issues(IssueID,ComicID,Location,Status) VALUES(?,?,?,?)',('321','456','other/missing.cbz','Wanted'))
  real=self.api.Api._successResponse;fired=[]
  def serializer(handler,result):
   raw=real(handler,result);missing.write_bytes(b'late physical catalog claim');fired.append(True);return raw
  with patch.object(self.api.Api,'_successResponse',serializer):self.assertFalse(self.call()['success'])
  self.assertTrue(fired)
 def test_native_review_sanitized_and_startup_pending_no_grant(self):
  with patch.object(self.n,'_STARTUP_COMPLETE',False):self.assertFalse(self.call()['success'])
  with patch.object(fixture.r,'prepare_existing',side_effect=self.base.native.Review('original review')):self.assertFalse(self.call()['success'])
  self.assertFalse((self.c.c.root/fixture.r.NAME).exists())
 def test_nonpassive_commands_still_take_default_operation(self):
  self.handler.cmd='unrelated';self.assertFalse(self.n.self_admitted_api(self.handler))
  self.assertNotIn('retainedDeliveryFinalize',self.n.PASSIVE_API);self.assertNotIn('retainedDeliveryStatus',self.n.PASSIVE_API)
 def test_source_frame_and_encoded_response_cannot_hydrate_from_json(self):
  with self.assertRaises(fixture.o.Held):fixture.f.ResponseSources({'files9':[]})
  with self.assertRaises(fixture.o.Held):fixture.f._close_response(object(),json.dumps({'success':True,'data':{}}))
 def test_late_config_revocation_inside_final_source_read_is_held(self):
  real=fixture.o.read_checked;fired=[]
  def late(path,*args,**kwargs):
   raw=real(path,*args,**kwargs)
   if Path(path)==ROOT/'publication_retained_api.py' and fixture.f._HTTP and not fired:
    self.pkg.CONFIG.API_KEY='z'*32;fired.append(True)
   return raw
  with patch.object(fixture.o,'read_checked',late):self.assertFalse(self.call()['success'])
  self.assertTrue(fired)
 def test_changed_workflow_after_original_completion_never_reseals_status(self):
  self.assertTrue(self.call()['success']);self.c.store.set('meta','foreign','later')
  before=self.c.c.database.read_bytes();self.assertFalse(self.call('retainedDeliveryStatus')['success'])
  self.assertEqual(self.c.c.database.read_bytes(),before)

 def test_spoofed_hook_metadata_never_falls_back_to_recovery_purpose(self):
  fired=[]
  def foreign(handler,**kwargs):fired.append(True);handler.data=json.dumps({'success':True,'data':{'foreign':True}})
  foreign.__module__='mylar.api';foreign.__qualname__='Api._retainedDeliveryFinalize'
  with patch.object(self.api.Api,'_retainedDeliveryFinalize',foreign):self.assertFalse(self.call()['success'])
  self.assertFalse(fired);self.assertFalse((self.c.c.root/fixture.r.NAME).exists())

 def test_actual_pending_marker_blocks_before_producer(self):
  marker=self.c.writer.pending;marker.write_bytes(b'original pending')
  self.assertFalse(self.call()['success']);self.assertEqual(marker.read_bytes(),b'original pending')
  self.assertFalse((self.c.c.root/fixture.r.NAME).exists())
 def test_duplicate_encoded_success_envelope_is_refused(self):
  real=self.api.Api._successResponse
  def serializer(handler,result):return real(handler,result).replace('{','{"success":true,',1)
  with patch.object(self.api.Api,'_successResponse',serializer):self.assertFalse(self.call()['success'])
 def test_final_helper_binding_replacement_never_gets_response(self):
  real=fixture.r._writer_binding;fired=[]
  def late(writer):
   result=real(writer)
   if sys._getframe(1).f_code.co_name=='_finish_response' and not fired:
    writer.pending=writer.root/'foreign-pending';fired.append(True)
   return result
  with patch.object(fixture.r,'_writer_binding',late):self.assertFalse(self.call()['success'])
  self.assertTrue(fired)

if __name__=='__main__':unittest.main()
