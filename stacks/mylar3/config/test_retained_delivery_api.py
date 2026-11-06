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
import patch_publication_startup as startup_installer

ROOT=Path(__file__).parent
API_SHA='7cd81fc5e511f27d0943507df7606df68f660ffe6688677b937eafba92a00c6a'

class Endpoint(unittest.TestCase):
 def setUp(self):
  self.base=actual.Controls('runTest');self.base.setUp();self.addCleanup(self.base.doCleanups)
  self.c=self.base.c;self.n=self.base.n;self.pkg=sys.modules['mylar'];self.pkg.CONFIG.API_ENABLED=True;self.pkg.CONFIG.API_KEY='x'*32
  self.http=SimpleNamespace(request=SimpleNamespace(method='POST'),response=SimpleNamespace(headers={}))
  ctx=patch.dict(sys.modules,{'cherrypy':self.http});ctx.start();self.addCleanup(ctx.stop)
  physical=ROOT/'api.py';before=physical.read_bytes()
  source=(ROOT.parent/'preimages/api.py').read_text()
  self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),API_SHA)
  source=installer.patched_source(source)
  self.assertEqual(source.count(startup_installer.OLD_API_PREFIX),1)
  source=source.replace(startup_installer.OLD_API_PREFIX,startup_installer.API_PREFIX,1)
  physical.write_text(source)
  self.addCleanup(physical.write_bytes,before)
  tree=ast.parse(source);node=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Api')
  keep={'checkParams','_successResponse','_failureResponse','fetchData','_retainedDeliveryFinalize','_retainedDeliveryStatus','_retainedDeliverySession'}
  node.body=[x for x in node.body if isinstance(x,ast.FunctionDef) and x.name in keep]
  module=ModuleType('mylar.api');module.__file__=str(physical)
  self.pkg.SSE_KEY='s'*32
  module.__dict__.update(cmd_list=list(installer.COMMANDS)+['getIndex'],mylar=self.pkg,cherrypy=self.http,json=json,native_writers=self.n,API_ERROR_CODE_DEFAULT=0,
                         logger=SimpleNamespace(fdebug=lambda value:None))
  ctx=patch.dict(sys.modules,{'mylar.api':module});ctx.start();self.addCleanup(ctx.stop)
  ctx=patch.object(self.pkg,'api',module,create=True);ctx.start();self.addCleanup(ctx.stop)
  exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(physical),'exec'),module.__dict__)
  self.api=module
  spec=importlib.util.spec_from_file_location('mylar.publication_retained_api',ROOT/'publication_retained_api.py');self.endpoint=importlib.util.module_from_spec(spec)
  ctx=patch.dict(sys.modules,{spec.name:self.endpoint});ctx.start();self.addCleanup(ctx.stop);spec.loader.exec_module(self.endpoint)
  ctx=patch.object(self.pkg,'publication_retained_api',self.endpoint,create=True);ctx.start();self.addCleanup(ctx.stop)
  self.handler=object.__new__(module.Api)
  self.handler.__dict__.update(cmd='retainedDeliveryFinalize',apikey='x'*32,apitype='normal',headers='application/json',
                              kwargs={'request':self.base.raw()},img=None,file=None,comicrn=False,data='OK')
 def call(self,command='retainedDeliveryFinalize',raw=None,*,apikey=None):
  self.handler.checkParams(cmd=command,apikey=self.pkg.CONFIG.API_KEY if apikey is None else apikey,request=raw if raw is not None else self.base.raw())
  return json.loads(self.handler.fetchData())
 def session_call(self,action,nonce='9'*64,proof=None):
  body=dict(version=1,kind='retained-native-session-v1',action=action,nonce=nonce,
            request=json.loads(self.base.raw()),proof=proof)
  self.handler.checkParams(cmd='retainedDeliverySession',apikey=self.pkg.CONFIG.API_KEY,request=json.dumps(body))
  return json.loads(self.handler.fetchData())
 def test_actual_broker_session_packet_is_accepted_by_actual_handler(self):
  spec=importlib.util.spec_from_file_location('retained_broker_wire',ROOT/'standalone_launch_host/comic_retained_standalone_broker.py')
  broker=importlib.util.module_from_spec(spec);spec.loader.exec_module(broker)
  boot=dict(nonce='9'*64,request=json.loads(self.base.raw()))
  packet=broker.native_session_request(boot,'open')
  self.handler.checkParams(cmd='retainedDeliverySession',apikey=self.pkg.CONFIG.API_KEY,request=json.dumps(packet))
  answer=json.loads(self.handler.fetchData());self.assertTrue(answer['success'])
  self.assertIsNotNone(self.endpoint._ROOT_SESSION)
  packet=broker.native_session_request(boot,'observe')
  self.handler.checkParams(cmd='retainedDeliverySession',apikey=self.pkg.CONFIG.API_KEY,request=json.dumps(packet))
  self.assertEqual(json.loads(self.handler.fetchData())['data']['state'],'active-original-process')

 def test_native_session_blocks_background_but_allows_exact_retained_action(self):
  before=self.c.c.database.read_bytes();opened=self.session_call('open')
  self.assertTrue(opened['success']);self.assertEqual(self.c.c.database.read_bytes(),before)
  with self.assertRaisesRegex(sys.modules['mylar.media_writer'].Busy,'reserved'):
   with self.n.operation():self.fail('Background operation entered reservation')
  self.assertEqual(self.n._OPERATIONS,0)
  self.assertTrue(self.pkg.CONFIG.API_ENABLED)
  self.assertEqual(self.session_call('observe')['data']['state'],'active-original-process')
  answer=self.call();self.assertTrue(answer['success'])
  self.assertEqual(self.call('retainedDeliveryStatus'),answer)
  self.assertTrue((self.c.c.writer_root/self.endpoint._SESSION_PENDING).is_file())
 def test_native_session_rejects_busy_duplicate_foreign_and_restarted_contexts(self):
  with patch.object(self.n,'_OPERATIONS',1):self.assertFalse(self.session_call('open')['success'])
  self.assertIsNone(self.endpoint._ROOT_SESSION)
  self.assertTrue(self.session_call('open')['success']);record=self.endpoint._ROOT_SESSION
  self.assertFalse(self.session_call('open')['success'])
  self.assertFalse(self.session_call('observe',nonce='8'*64)['success'])
  with patch.object(self.endpoint,'_ROOT_SESSION',None):
   with self.assertRaisesRegex(sys.modules['mylar.media_writer'].Busy,'original-process review'):
    with self.n.operation():self.fail('Saved marker minted live reservation')
   self.assertEqual(self.session_call('observe')['data']['state'],'factual-held')
   self.assertFalse(self.session_call('close',proof={})['success'])
  self.assertIs(self.endpoint._ROOT_SESSION,record)
 def test_native_session_close_requires_complete_actual_terminal_SQL(self):
  self.assertTrue(self.session_call('open')['success']);answer=self.call();self.assertTrue(answer['success'])
  r=fixture.r
  def model(path):return r._sql(path,r.o.signature(path))
  digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
  proof=dict(workflow_sha256=digest(model(self.c.c.database)),catalog_sha256=digest(model(self.c.c.native_database)),
             record_sha256=answer['data']['record_sha256'],root_release_nonce='7'*64,worker_ack_sha256='6'*64)
  bad=dict(proof,workflow_sha256='0'*64)
  self.assertFalse(self.session_call('close',proof=bad)['success'])
  self.assertIsNotNone(self.endpoint._ROOT_SESSION)
  closed=self.session_call('close',proof=proof);self.assertTrue(closed['success'])
  self.assertEqual(closed['data']['proof'],proof)
  self.assertIsNone(self.endpoint._ROOT_SESSION)
  self.assertFalse((self.c.c.writer_root/self.endpoint._SESSION_PENDING).exists())
  self.assertFalse((self.c.c.writer_root/self.endpoint._SESSION_CLOSED).exists())
  history=self.c.c.writer_root/self.endpoint._SESSION_HISTORY/('9'*64)
  self.assertEqual(sorted(p.name for p in history.iterdir()),['closed.json','pending.json'])
  self.assertEqual(json.loads((history/'closed.json').read_bytes())['proof'],proof)
  self.assertTrue(all(p.stat().st_nlink==1 for p in history.iterdir()))
  with self.n.operation():pass
  from mylar import publication_api,publication_guard
  with patch.object(publication_api,'__package__','mylar'),patch.object(publication_guard,'__package__','mylar'):
   self.assertEqual(self.n.startup_status()['state'],'ready')
   with self.n.owner().hold(timeout=0) as writer:publication_api._ordinary_native_session(writer)
  self.assertFalse(self.session_call('close',proof=proof)['success'])
  with patch.object(self.endpoint,'_ROOT_SESSION',None):
   self.assertEqual(self.n.startup_status()['state'],'ready')
   with self.n.operation():pass
  self.assertFalse(self.session_call('open')['success'])
  self.assertTrue(self.session_call('open',nonce='8'*64)['success'])
 def test_closed_without_pending_or_live_custody_is_negative_evidence(self):
  marker=self.c.c.writer_root/self.endpoint._SESSION_CLOSED
  marker.write_bytes(b'{"untrusted":"saved-completion"}');marker.chmod(0o600)
  self.assertIsNone(self.endpoint._ROOT_SESSION)
  self.assertEqual(self.n.startup_status()['reason'],'retained-session')
  with self.assertRaises(sys.modules['mylar.media_writer'].Busy):
   with self.n.operation():self.fail('Saved close receipt granted ordinary admission')
  from mylar import publication_api
  with self.n.owner().hold(timeout=0) as writer,self.assertRaises(publication_api.guard.Unavailable):
   publication_api._ordinary_native_session(writer)
 def test_retained_session_router_keeps_ordinary_commands_held(self):
  self.assertTrue(self.session_call('open')['success'])
  self.assertFalse(self.call('getIndex')['success'])
  with patch.object(self.endpoint,'_ROOT_SESSION',None):
   self.assertFalse(self.call()['success'])
   self.assertEqual(self.session_call('observe')['data']['state'],'factual-held')

 def test_publication_control_raw_writer_paths_refuse_reserved_marker(self):
  self.assertTrue(self.session_call('open')['success'])
  from mylar import publication_api
  with self.n.owner().hold(timeout=0) as writer:
   with self.assertRaisesRegex(publication_api.guard.Unavailable,'reserved'):
    publication_api._ordinary_native_session(writer)

 def test_native_session_status_and_health_are_held_without_SQL_access(self):
  self.assertTrue(self.session_call('open')['success'])
  self.assertEqual(self.n.startup_status(),dict(version=1,state='held',reason='retained-session',census=None))
  spec=importlib.util.spec_from_file_location('mylar.worker_health',ROOT/'worker_health.py')
  health=importlib.util.module_from_spec(spec);spec.loader.exec_module(health)
  with patch.object(health,'_snapshot',side_effect=AssertionError('Reserved health read SQL')):
   answer=health.snapshot()
  self.assertEqual(answer['publication']['reason'],'retained-session')
  self.assertNotIn('busy_workers',answer)
  with patch.object(self.endpoint,'_ROOT_SESSION',None):
   self.assertEqual(self.n.initialize_publication()['reason'],'retained-session')
   self.assertEqual(self.n.startup_status()['state'],'held')
   self.assertEqual(health.snapshot()['publication']['state'],'held')
 def test_live_session_remains_held_after_pending_marker_disappears(self):
  self.assertTrue(self.session_call('open')['success'])
  (self.c.c.writer_root/self.endpoint._SESSION_PENDING).unlink()
  self.assertEqual(self.n.startup_status()['reason'],'retained-session')
  with self.assertRaises(sys.modules['mylar.media_writer'].Busy):
   with self.n.operation():self.fail('Lost marker bypassed live custody')
  from mylar import publication_api
  with patch.object(publication_api,'__package__','mylar'):
   with patch.object(self.c.c,'_dispatch',side_effect=AssertionError('Raw dispatch entered reservation')):
    with self.assertRaises(publication_api.guard.Unavailable):
     self.c.c.dispatch(dict(action='review'))
 def test_reserved_fresh_preparation_is_refused_before_preparer(self):
  self.assertTrue(self.session_call('open')['success'])
  from mylar import publication_api
  preparer=ModuleType('mylar.publication_fresh')
  preparer.prepare=lambda *a,**k:self.fail('Fresh preparation ran while reserved')
  with patch.object(publication_api,'__package__','mylar'),patch.dict(sys.modules,{'mylar.publication_fresh':preparer}):
   with self.assertRaises(sys.modules['mylar.media_writer'].Busy):
    self.c.c.dispatch(dict(action='prepare-fresh',backup={},epoch=0))

 def test_tick_advisory_ready_to_reservation_race_is_harmless(self):
  tree=ast.parse((ROOT/'workflow.py').read_text())
  node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='tick')
  module=ModuleType('mylar.reservation_tick');module.__package__='mylar'
  module._tick=lambda queue:self.fail('Reserved tick entered workflow')
  exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(ROOT/'workflow.py'),'exec'),module.__dict__)
  self.assertTrue(self.session_call('open')['success'])
  module.tick(None)
  with patch.object(self.n,'startup_status',return_value=dict(state='ready')):
   module.tick(None)
  self.assertEqual(self.n._OPERATIONS,0)
 def test_native_session_open_cannot_overlap_actual_counted_operation(self):
  import threading
  entered=threading.Event();release=threading.Event();failures=[]
  def ordinary():
   try:
    with self.n.operation():
     entered.set()
     if not release.wait(10):raise AssertionError('Test release missing')
   except BaseException as error:failures.append(error);entered.set()
  thread=threading.Thread(target=ordinary);thread.start()
  try:
   self.assertTrue(entered.wait(10));self.assertFalse(failures)
   self.assertFalse(self.session_call('open')['success'])
   self.assertIsNone(self.endpoint._ROOT_SESSION)
   self.assertFalse((self.c.c.writer_root/self.endpoint._SESSION_PENDING).exists())
  finally:release.set();thread.join(10)
  self.assertFalse(thread.is_alive());self.assertFalse(failures)
  self.assertEqual(self.n._OPERATIONS,0)
  self.assertTrue(self.session_call('open')['success'])
 def test_native_session_close_fsync_failure_keeps_restart_fence(self):
  self.assertTrue(self.session_call('open')['success']);answer=self.call();self.assertTrue(answer['success'])
  r=fixture.r
  digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
  proof=dict(workflow_sha256=digest(r._sql(self.c.c.database,r.o.signature(self.c.c.database))),
   catalog_sha256=digest(r._sql(self.c.c.native_database,r.o.signature(self.c.c.native_database))),
   record_sha256=answer['data']['record_sha256'],root_release_nonce='7'*64,worker_ack_sha256='6'*64)
  pending=self.c.c.writer_root/self.endpoint._SESSION_PENDING;real_fsync=os.fsync
  def failed(fd):
   if (self.c.c.writer_root/self.endpoint._SESSION_CLOSED).exists():raise OSError('Synthetic close sync failure')
   return real_fsync(fd)
  with patch.object(self.endpoint.os,'fsync',failed):
   self.assertFalse(self.session_call('close',proof=proof)['success'])
  self.assertTrue(pending.exists());self.assertIsNotNone(self.endpoint._ROOT_SESSION)
  with patch.object(self.endpoint,'_ROOT_SESSION',None):
   self.assertEqual(self.n.startup_status()['reason'],'retained-session')
  self.assertEqual(self.n.startup_status()['reason'],'retained-session')
  from mylar import publication_api
  with patch.object(publication_api,'__package__','mylar'),self.assertRaises(publication_api.guard.Unavailable):
   self.c.c.dispatch(dict(action='review'))

 def test_native_session_late_retirement_sync_failure_restores_restart_fence(self):
  self.assertTrue(self.session_call('open')['success']);answer=self.call();self.assertTrue(answer['success'])
  r=fixture.r
  digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
  proof=dict(workflow_sha256=digest(r._sql(self.c.c.database,r.o.signature(self.c.c.database))),
   catalog_sha256=digest(r._sql(self.c.c.native_database,r.o.signature(self.c.c.native_database))),
   record_sha256=answer['data']['record_sha256'],root_release_nonce='7'*64,worker_ack_sha256='6'*64)
  root=self.c.c.writer_root;real_fsync=os.fsync;failed_once=[]
  def failed(fd):
   if not failed_once and not any((root/name).exists() for name in (self.endpoint._SESSION_PENDING,self.endpoint._SESSION_CLOSED)):
    failed_once.append(True);raise OSError('Synthetic final commit sync failure')
   return real_fsync(fd)
  with patch.object(self.endpoint.os,'fsync',failed):
   self.assertFalse(self.session_call('close',proof=proof)['success'])
  self.assertTrue(failed_once);self.assertIsNotNone(self.endpoint._ROOT_SESSION)
  self.assertTrue((root/self.endpoint._SESSION_CLOSED).is_file())
  with patch.object(self.endpoint,'_ROOT_SESSION',None):
   self.assertEqual(self.n.startup_status()['reason'],'retained-session')

 def test_native_session_Writer_exit_failure_restores_restart_fence(self):
  from contextlib import contextmanager
  self.assertTrue(self.session_call('open')['success']);answer=self.call();self.assertTrue(answer['success'])
  r=fixture.r
  digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
  proof=dict(workflow_sha256=digest(r._sql(self.c.c.database,r.o.signature(self.c.c.database))),
   catalog_sha256=digest(r._sql(self.c.c.native_database,r.o.signature(self.c.c.native_database))),
   record_sha256=answer['data']['record_sha256'],root_release_nonce='7'*64,worker_ack_sha256='6'*64)
  root=self.c.c.writer_root;writer_type=type(self.n.owner());hold=writer_type.hold;failed=[]
  @contextmanager
  def uncertain(writer,*args,**kwargs):
   with hold(writer,*args,**kwargs):yield writer
   if not any((root/name).exists() for name in (self.endpoint._SESSION_PENDING,self.endpoint._SESSION_CLOSED)):
    failed.append(True);raise OSError('Synthetic Writer exit uncertainty')
  with patch.object(writer_type,'hold',uncertain):
   self.assertFalse(self.session_call('close',proof=proof)['success'])
  self.assertEqual(failed,[True]);self.assertIsNotNone(self.endpoint._ROOT_SESSION)
  self.assertTrue((root/self.endpoint._SESSION_CLOSED).exists())
  with patch.object(self.endpoint,'_ROOT_SESSION',None):
   self.assertEqual(self.n.startup_status()['reason'],'retained-session')

 def test_retirement_recloses_copies_at_each_sync_boundary(self):
  import tempfile
  endpoint=self.endpoint;real_fsync=os.fsync
  for fault in range(1,7):
   with self.subTest(sync=fault),tempfile.TemporaryDirectory() as directory:
    root=Path(directory);history=root/'history';history.mkdir(mode=0o700)
    marker=b'pending';closed=b'closed'
    pending9=endpoint._session_save(root,endpoint._SESSION_PENDING,marker)
    closed9=endpoint._session_save(root,endpoint._SESSION_CLOSED,closed)
    record=SimpleNamespace(root=root,root5=endpoint._session_five(root.stat()),history=history,
     history5=endpoint._session_five(history.stat()),history_parent5=endpoint._session_five(root.stat()),
     marker_bytes=marker,marker9=pending9,files=(),nodes=())
    calls=[]
    def failed(fd):
     calls.append(fd)
     if len(calls)==fault:raise OSError('Synthetic retirement sync failure')
     return real_fsync(fd)
    with patch.object(endpoint,'_ROOT_SESSION',record),patch.object(endpoint.os,'fsync',failed):
     with self.assertRaisesRegex(OSError,'Synthetic retirement'):
      try:endpoint._session_retire(record,closed9,((),(),()))
      except BaseException:
       endpoint._session_refence(record,closed);raise
    self.assertTrue(any((root/name).exists() for name in (endpoint._SESSION_PENDING,endpoint._SESSION_CLOSED)))

 def test_retirement_detects_postcommit_history_replacement_and_closes_failed_open(self):
  import tempfile
  endpoint=self.endpoint;real_fsync=os.fsync;real_open=os.open
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);history=root/'history';history.mkdir(mode=0o700)
   pending9=endpoint._session_save(root,endpoint._SESSION_PENDING,b'pending')
   closed9=endpoint._session_save(root,endpoint._SESSION_CLOSED,b'closed')
   record=SimpleNamespace(root=root,root5=endpoint._session_five(root.stat()),history=history,
    history5=endpoint._session_five(history.stat()),history_parent5=endpoint._session_five(root.stat()),
    marker_bytes=b'pending',marker9=pending9,files=(),nodes=())
   before=set(os.listdir('/proc/self/fd'))
   def refused(path,*args,**kwargs):
    if path==history:raise OSError('Synthetic history open failure')
    return real_open(path,*args,**kwargs)
   with patch.object(endpoint.os,'open',refused),self.assertRaises(OSError):
    endpoint._session_retire(record,closed9,((),(),()))
   self.assertEqual(set(os.listdir('/proc/self/fd')),before)
   changed=[]
   def corrupt(fd):
    if not changed and not (root/endpoint._SESSION_PENDING).exists():
     changed.append(True);p=history/'closed.json';p.unlink();p.write_bytes(b'closed');p.chmod(0o600)
    return real_fsync(fd)
   with patch.object(endpoint,'_ROOT_SESSION',record),patch.object(endpoint.os,'fsync',corrupt):
    with self.assertRaises(ValueError):
     try:endpoint._session_retire(record,closed9,((),(),()))
     except BaseException:
      endpoint._session_refence(record,b'closed');raise
   self.assertTrue(changed);self.assertTrue((root/endpoint._SESSION_CLOSED).exists())

 def test_reserved_liveness_needs_original_custody_but_not_external_Writer(self):
  import threading
  self.assertTrue(self.session_call('open')['success']);record=self.endpoint._ROOT_SESSION
  spec=importlib.util.spec_from_file_location('mylar.worker_health',ROOT/'worker_health.py')
  health=importlib.util.module_from_spec(spec);spec.loader.exec_module(health)
  values=dict(POST_PROCESSING=False,ENABLE_DDL=False,NZB_DOWNLOADER=0,NZBGET_CLIENT_POST_PROCESSING=False,
   SAB_CLIENT_POST_PROCESSING=False,ENABLE_TORRENTS=False,AUTO_SNATCH=False,TORRENT_DOWNLOADER=0)
  for name,value in values.items():setattr(self.pkg.CONFIG,name,value)
  self.pkg.OS_DETECT='Linux'
  queues=ModuleType('mylar.queues');rows=[SimpleNamespace(name='SEARCH-QUEUE',is_alive=True,size=0)]
  queues.queue_info=lambda:rows
  entered=threading.Event();release=threading.Event();errors=[]
  def hold():
   try:
    with self.n.owner().hold():
     entered.set()
     if not release.wait(10):raise AssertionError('Test release missing')
   except BaseException as error:errors.append(error);entered.set()
  thread=threading.Thread(target=hold);thread.start()
  try:
   self.assertTrue(entered.wait(10));self.assertFalse(errors)
   with patch.dict(sys.modules,{'mylar.queues':queues}),patch.object(health,'_snapshot',side_effect=AssertionError('Reserved health read SQL')),patch('sqlite3.connect',side_effect=AssertionError('Reserved health opened SQL')):
    sample=health.snapshot()
    self.assertEqual(sample['publication'],dict(version=1,state='held',reason='retained-session',census=None))
    self.assertTrue(sample['busy_workers']['queues']['SEARCH-QUEUE']['alive'])
    with patch.object(self.endpoint,'_ROOT_SESSION',None):
     self.assertNotIn('busy_workers',health.snapshot())
    with patch.object(self.endpoint.time,'monotonic',return_value=record.deadline):
     self.assertNotIn('busy_workers',health.snapshot())
    original=queues.queue_info
    def replaced():
     result=original();self.endpoint._ROOT_SESSION=record._replace(pid=record.pid+1);return result
    with patch.object(queues,'queue_info',replaced):
     self.assertNotIn('busy_workers',health.snapshot())
    self.endpoint._ROOT_SESSION=record
    (self.c.c.writer_root/self.endpoint._SESSION_PENDING).unlink()
    (self.c.c.writer_root/self.endpoint._SESSION_CLOSED).write_bytes(b'untrusted-saved-closure')
    with patch.object(self.endpoint,'_ROOT_SESSION',None):
     orphan=health.snapshot()
     self.assertEqual(orphan['publication']['reason'],'retained-session')
     self.assertNotIn('busy_workers',orphan)
  finally:
   release.set();thread.join(10)
  self.assertFalse(thread.is_alive());self.assertFalse(errors)

 def test_original_session_spans_distinct_live_HTTP_threads_and_handlers(self):
  import threading
  release=threading.Event();threads=[];errors=[];results={};identities=[]
  defaults=dict(self.handler.__dict__)
  def invoke(name,command,raw):
   finished=threading.Event()
   def request():
    try:
     handler=object.__new__(self.api.Api);handler.__dict__.update(defaults)
     handler.checkParams(cmd=command,apikey=self.pkg.CONFIG.API_KEY,request=raw)
     results[name]=json.loads(handler.fetchData());identities.append(threading.get_ident())
    except BaseException as error:errors.append(error)
    finally:
     finished.set()
     if not release.wait(30):errors.append(AssertionError('HTTP fixture release missing'))
   thread=threading.Thread(target=request);threads.append(thread);thread.start()
   self.assertTrue(finished.wait(30));self.assertFalse(errors)
   self.assertTrue(results[name]['success'],results[name])
   return results[name]
  request=json.loads(self.base.raw())
  def session(action,proof=None):
   return json.dumps(dict(version=1,kind='retained-native-session-v1',action=action,
    nonce='9'*64,request=request,proof=proof))
  try:
   invoke('open','retainedDeliverySession',session('open'))
   answer=invoke('finalize','retainedDeliveryFinalize',self.base.raw())
   self.assertEqual(invoke('status','retainedDeliveryStatus',self.base.raw()),answer)
   r=fixture.r
   digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
   proof=dict(workflow_sha256=digest(r._sql(self.c.c.database,r.o.signature(self.c.c.database))),
    catalog_sha256=digest(r._sql(self.c.c.native_database,r.o.signature(self.c.c.native_database))),
    record_sha256=answer['data']['record_sha256'],root_release_nonce='7'*64,worker_ack_sha256='6'*64)
   invoke('close','retainedDeliverySession',session('close',proof))
   self.assertEqual(len(identities),4);self.assertEqual(len(set(identities)),4)
   self.assertTrue(all(thread.is_alive() for thread in threads))
  finally:
   release.set()
   for thread in threads:thread.join(30)
   self.assertFalse(any(thread.is_alive() for thread in threads))
  self.assertFalse(errors);self.assertEqual(self.n._OPERATIONS,0)

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
  for key in ('y'*32,self.pkg.SSE_KEY):
   self.assertFalse(self.call(apikey=key)['success'])
  for field,value in [('API_ENABLED',False),('API_KEY','short')]:
   with patch.object(self.pkg.CONFIG,field,value):self.assertFalse(self.call()['success'])
  with patch.object(self.http.request,'method','GET'):self.assertFalse(self.call()['success'])
  self.handler.kwargs={'request':self.base.raw(),'callback':'foreign'};self.handler.data='OK'
  self.handler._retainedDeliveryFinalize(**self.handler.kwargs);self.assertFalse(json.loads(self.handler.data)['success'])
  self.assertFalse((self.c.c.root/fixture.r.NAME).exists())
 def test_writer_setup_cannot_rebase_original_API_source_frame(self):
  from contextlib import contextmanager
  cls=fixture.fixture.writers.Writer;original=cls.hold
  for mutation in ('replace','equal','erase','extend'):
   with self.subTest(mutation=mutation):
    self.setUp();fired=[]
    @contextmanager
    def changed(writer,**kwargs):
     if not fired:
      entries=list(fixture.f._SOURCE_FRAMES.items())
      if entries:
       frame,source=entries[-1];fired.append(True)
       if mutation=='erase':fixture.f._SOURCE_FRAMES.pop(frame)
       else:
        replacement=list(source)
        if mutation=='replace':replacement[3]=b'{}'
        if mutation=='extend':replacement[2]+=3600
        fixture.f._SOURCE_FRAMES[frame]=tuple(replacement)
     with original(writer,**kwargs):yield writer
    with patch.object(cls,'hold',changed):self.assertFalse(self.call()['success'])
    self.assertTrue(fired);self.assertFalse((self.c.c.root/fixture.r.NAME).exists())

 def test_status_cannot_become_finalize_during_source_capture(self):
  original=fixture.f.response_sources
  def changed():
   source=original();self.handler.cmd='retainedDeliveryFinalize';return source
  before=self.c.c.database.read_bytes()
  with patch.object(fixture.f,'response_sources',changed):
   self.assertFalse(self.call('retainedDeliveryStatus')['success'])
  self.assertEqual(self.c.c.database.read_bytes(),before)
  self.assertFalse((self.c.c.root/fixture.r.NAME).exists())

 def test_handler_code_cannot_become_admission_original_after_capture(self):
  original=fixture.f.response_sources;method=self.api.Api._retainedDeliveryFinalize;code=method.__code__
  def changed():
   source=original();method.__code__=self.api.Api._retainedDeliveryStatus.__code__;return source
  try:
   with patch.object(fixture.f,'response_sources',changed):self.assertFalse(self.call()['success'])
  finally:method.__code__=code
  self.assertFalse((self.c.c.root/fixture.r.NAME).exists())

 def test_admission_deadline_closes_after_last_source_read(self):
  original=fixture.o.read_checked;clock=fixture.f.time.monotonic;expired=[]
  def monotonic():return clock()+(1000000 if expired else 0)
  def late(path,*args,**kwargs):
   result=original(path,*args,**kwargs)
   active=[seal for seal in self.endpoint._ADMISSION_SEALS.values()
           if seal[0]['phase']=='admitted' and str(path)==seal[12][-1][0]]
   if active:expired.append(True)
   return result
  with patch.object(self.endpoint.time,'monotonic',monotonic),patch.object(fixture.o,'read_checked',late):
   self.assertFalse(self.call()['success'])
  self.assertTrue(expired);self.assertFalse((self.c.c.root/fixture.r.NAME).exists())

 def test_actual_admission_enters_disabled_direct_kernels(self):
  with patch.object(fixture.r,'ENABLED',False),patch.object(fixture.f,'ENABLED',False):
   with self.c.writer.hold():
    with self.assertRaises(fixture.o.Held):fixture.r.prepare_existing(self.c.c,self.c.writer,self.c.body)
   self.assertFalse((self.c.c.root/fixture.r.NAME).exists())
   result=self.call();self.assertTrue(result['success']);self.assertFalse(result['data']['ordinary_import_grant'])

 def test_saved_or_foreign_native_admission_is_not_a_factory(self):
  with self.assertRaises(ValueError):self.endpoint.NativeRetainedAdmission({})
  fake=object.__new__(self.endpoint.NativeRetainedAdmission)
  with self.c.writer.hold():
   with self.assertRaises(ValueError):
    fixture.r.prepare_existing(self.c.c,self.c.writer,self.c.body,admission=fake)
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
   if (not getattr(writer.local[1],'depth',0) and not fired
       and 'closed' in self.endpoint._ADMISSION_PHASES.values()):
    self.c.case.target.chmod(0o640);fired.append(True)
  with patch.object(cls,'hold',late):self.assertFalse(self.call()['success'])
  self.assertTrue(fired)
 def test_saved_response_receipt_constructor_and_repeat_refuse(self):
  answer=self.call();self.assertTrue(answer['success'])
  with self.assertRaises(fixture.o.Held):fixture.f.RetainedFinalization(answer['data'])
  self.assertFalse(self.call()['success'])
 def test_sameprocess_registry_missing_is_not_hydrated_from_saved_sql(self):
  answer=self.call();key=(str(self.c.c.root),answer['data']['token']);old=fixture.f._FINALS.pop(key)
  try:
   result=self.call('retainedDeliveryStatus');self.assertTrue(result['success'])
   self.assertEqual(result['data']['outcome'],'retained-durable-state-observed')
   self.assertNotIn(key,fixture.f._FINALS)
  finally:fixture.f._FINALS[key]=old
 def test_passive_status_after_registry_loss_does_not_recreate_authority(self):
  answer=self.call();self.assertTrue(answer['success'])
  key=(str(self.c.c.root),answer['data']['token'])
  fixture.f._FINALS.pop(key);fixture.r._EVENTS.pop(key)
  before=self.c.c.database.read_bytes();catalog=self.c.c.native_database.read_bytes()
  result=self.call('retainedDeliveryStatus')
  self.assertTrue(result['success']);self.assertEqual(result['data']['outcome'],'retained-durable-state-observed')
  for name in ('historical_import_ack','ordinary_import_grant','cleanup_grant','mutation_authority',
               'publication_acceptance','reader_index_acceptance','automatic_replay','reader_resume_grant',
               'operational_custody_complete'):self.assertIs(result['data'][name],False)
  self.assertNotIn(key,fixture.f._FINALS);self.assertNotIn(key,fixture.r._EVENTS)
  self.assertFalse(self.call()['success'])
  self.assertEqual(self.c.c.database.read_bytes(),before);self.assertEqual(self.c.c.native_database.read_bytes(),catalog)

 def test_passive_status_in_new_process_without_live_registries(self):
  answer=self.call();self.assertTrue(answer['success'])
  read_fd,write_fd=os.pipe();pid=os.fork()
  if pid==0:
   try:
    os.close(read_fd);fixture.f._FINALS.clear();fixture.r._EVENTS.clear()
    fixture.f._RECEIPTS.clear();fixture.r._CORES.clear()
    result=self.call('retainedDeliveryStatus')
    packet=dict(result=result,finals=len(fixture.f._FINALS),events=len(fixture.r._EVENTS),
                replay=self.call()['success'])
    os.write(write_fd,json.dumps(packet).encode());os._exit(0)
   except BaseException:os._exit(2)
  os.close(write_fd)
  with os.fdopen(read_fd,'rb') as stream:raw=stream.read(65537)
  self.assertEqual(os.waitpid(pid,0)[1],0)
  result=json.loads(raw);self.assertTrue(result['result']['success'])
  self.assertEqual(result['result']['data']['outcome'],'retained-durable-state-observed')
  self.assertEqual((result['finals'],result['events'],result['replay']),(0,0,False))

 def test_passive_serializer_cannot_rebase_rights_or_original_vectors(self):
  for mutation in ('rights','zero-right','equal-frame','source-erasure','equal-source','current-binding','config'):
   with self.subTest(mutation=mutation):
    self.setUp();answer=self.call();self.assertTrue(answer['success'])
    key=(str(self.c.c.root),answer['data']['token'])
    fixture.f._FINALS.pop(key);fixture.r._EVENTS.pop(key)
    fired=[]
    def fault(frame,event,arg):
     if not fired and event=='return' and frame.f_code is self.api.Api._successResponse.__code__:
      active=[c for c in fixture.f._PASSIVE.values() if c['phase']=='encoding']
      if active:
       c=active[-1];fired.append(True)
       if mutation=='rights':c['result']['reader_resume_grant']=True
       elif mutation=='zero-right':c['result']['reader_resume_grant']=0
       elif mutation=='equal-frame':c['files']=dict(c['files'])
       elif mutation=='current-binding':c['controller'].roots=tuple(c['controller'].roots)+('/foreign',)
       elif mutation=='config':self.pkg.CONFIG.DDL_LOCATION+='foreign'
       else:
        obj=next(obj for obj,state in fixture.f._PASSIVE.items() if state is c)
        source=fixture.f._PASSIVE_SOURCES[obj]
        if mutation=='source-erasure':fixture.f._PASSIVE_SOURCES.pop(obj)
        else:fixture.f._PASSIVE_SOURCES[obj]=tuple(list(source))
    sys.setprofile(fault)
    try:result=self.call('retainedDeliveryStatus')
    finally:sys.setprofile(None)
    self.assertTrue(fired);self.assertFalse(result['success']);self.assertNotIn(key,fixture.f._FINALS)

 def test_passive_source_erasure_after_operation_exit_refuses(self):
  answer=self.call();self.assertTrue(answer['success']);key=(str(self.c.c.root),answer['data']['token'])
  fixture.f._FINALS.pop(key);fixture.r._EVENTS.pop(key)
  original=self.n.admission;calls=[]
  def late(writer,**kwargs):
   answer=original(writer,**kwargs);calls.append(True)
   if len(calls)==2:fixture.f._PASSIVE_SOURCES.clear()
   return answer
  with patch.object(self.n,'admission',late):self.assertFalse(self.call('retainedDeliveryStatus')['success'])
  self.assertEqual(len(calls),2)

 def passive_finish_fault(self,kind):
  answer=self.call();self.assertTrue(answer['success']);key=(str(self.c.c.root),answer['data']['token'])
  fixture.f._FINALS.pop(key);fixture.r._EVENTS.pop(key)
  real=fixture.o.read_checked;fired=[];held=[];method=self.api.Api._retainedDeliveryStatus;saved=method.__code__
  def changed(handler,request=None):pass
  def late(path,*args,**kwargs):
   raw=real(path,*args,**kwargs);frame=sys._getframe(1)
   if not fired and frame.f_code.co_name=='_passive_close' and frame.f_locals.get('held') is False:
    fired.append(True)
    if kind=='method':method.__code__=changed.__code__
    elif kind=='admission-table':self.endpoint._ADMISSION_SEALS.clear()
    else:
     manager=self.n.owner().hold(timeout=0);manager.__enter__();held.append(manager)
   return raw
  try:
   with patch.object(fixture.o,'read_checked',late):result=self.call('retainedDeliveryStatus')
  finally:
   method.__code__=saved
   for manager in reversed(held):manager.__exit__(None,None,None)
  self.assertTrue(fired);self.assertFalse(result['success'])
 def test_passive_finish_late_handler_code_change_refuses(self):self.passive_finish_fault('method')
 def test_passive_finish_late_admission_table_erasure_refuses(self):self.passive_finish_fault('admission-table')
 def test_passive_finish_late_actual_writer_reacquisition_refuses(self):self.passive_finish_fault('writer')

 def test_live_finish_admission_erasure_after_writer_release_refuses(self):
  cls=fixture.fixture.writers.Writer;real=cls.hold;fired=[]
  from contextlib import contextmanager
  @contextmanager
  def late(writer,**kwargs):
   with real(writer,**kwargs):yield writer
   if not getattr(writer.local[1],'depth',0) and fixture.f._HTTP and not fired:
    entry=next(iter(fixture.f._HTTP.values()));entry['packet']['api_admission']=None;fired.append(True)
  with patch.object(cls,'hold',late):self.assertFalse(self.call()['success'])
  self.assertTrue(fired)

 def test_live_finish_last_binding_helper_cannot_change_original_handler(self):
  real=fixture.r._writer_binding;fired=[]
  def late(writer):
   answer=real(writer);frame=sys._getframe(1)
   if frame.f_code.co_name=='_finish_response' and not fired:
    self.handler.cmd='retainedDeliveryStatus';fired.append(True)
   return answer
  with patch.object(fixture.r,'_writer_binding',late):self.assertFalse(self.call()['success'])
  self.assertTrue(fired)

 def test_prepared_core_admission_erasure_refuses_before_acceptance_journal(self):
  real=fixture.r.prepare_existing;fired=[]
  def changed(*args,**kwargs):
   cap=real(*args,**kwargs);fixture.r._CORES[cap]['api_admission']=None;fired.append(True);return cap
  with patch.object(fixture.r,'prepare_existing',changed):self.assertFalse(self.call()['success'])
  self.assertTrue(fired)
  self.assertEqual(list((self.c.c.root/fixture.r.NAME).glob('*/accepted.json')),[])

 def test_large_complete_workflow_uses_bounded_transition_commitment(self):
  self.c.store.set('foreign','large-history',{'payload':'x'*(5*1024**2)})
  before=fixture.r._sql(self.c.c.database,tuple(fixture.o.signature(self.c.c.database)))
  self.assertGreater(len(fixture.o.compact(before)),4*1024**2)
  self.handler.checkParams(cmd='retainedDeliveryFinalize',apikey=self.pkg.CONFIG.API_KEY,request=self.base.raw())
  wire=self.handler.fetchData();answer=json.loads(wire)
  self.assertTrue(answer['success']);self.assertLessEqual(len(wire.encode()),4*1024**2)
  transition=answer['data']['transition'];self.assertEqual(transition['version'],2)
  self.assertNotIn('workflow_before',transition)
  self.assertEqual(transition['workflow_before_sha256'],hashlib.sha256(fixture.o.compact(before)).hexdigest())

 def test_persistent_final_record_does_not_embed_prior_workflow_history(self):
  self.c.store.set('retained_delivery_final','old-history',{'retained_history':'x'*300000})
  answer=self.call();self.assertTrue(answer['success'])
  raw=answer['data']['transition']['record_bytes'];record=json.loads(raw)
  self.assertLess(len(raw.encode()),65536)
  self.assertNotIn('workflow_before',record)
  self.assertEqual(record['workflow_before_sha256'],
      answer['data']['transition']['workflow_before_sha256'])
  self.assertEqual(record['pack_before_row'],answer['data']['transition']['pack_before_row'])

 def test_passive_shared_event_validators_refuse_schema_identity_and_rights(self):
  answer=self.call();self.assertTrue(answer['success'])
  token=answer['data']['token'];folder=self.c.c.root/fixture.r.NAME/token
  ack=json.loads((folder/'accepted.json').read_bytes())
  issued=json.loads((folder/'issued.json').read_bytes());stamp=tuple(fixture.o.signature(folder/'issued.json'))
  import copy
  for key,value in (('version',True),('historical_import_ack',True),('mutation_authority',True),
                    ('reader_index_acceptance',True),('automatic_replay',True)):
   bad=copy.deepcopy(ack);bad[key]=value
   with self.assertRaises(fixture.o.Held):fixture.r.validate_ack_body(bad,self.c.body,token)
  for key,value in (('version',True),('kind','foreign'),('created_fd_identity6',[0]*6)):
   bad=copy.deepcopy(issued);bad[key]=value
   with self.assertRaises(fixture.o.Held):
    fixture.r.validate_issued_body(bad,self.c.body,token,stamp,issued['ack'],issued['intent'])
  foreign=list(stamp);foreign[6]+=1
  with self.assertRaises(fixture.o.Held):
   fixture.r.validate_issued_body(issued,self.c.body,token,tuple(foreign),issued['ack'],issued['intent'])

 def test_passive_status_refuses_extra_SQL_and_changed_target(self):
  answer=self.call();self.assertTrue(answer['success']);key=(str(self.c.c.root),answer['data']['token'])
  fixture.f._FINALS.pop(key);fixture.r._EVENTS.pop(key)
  with sqlite3.connect(self.c.c.database) as db:db.execute("INSERT INTO records VALUES ('foreign','new','changed',0.0)")
  self.assertFalse(self.call('retainedDeliveryStatus')['success'])
  with sqlite3.connect(self.c.c.database) as db:db.execute("DELETE FROM records WHERE kind='foreign'")
  self.c.case.target.chmod(0o640)
  self.assertFalse(self.call('retainedDeliveryStatus')['success'])

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
  status=self.call('retainedDeliveryStatus');self.assertTrue(status['success'])
  self.assertEqual(status['data']['outcome'],'retained-durable-state-observed')
  self.assertFalse(status['data']['operational_custody_complete']);self.assertFalse(self.call()['success'])
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
