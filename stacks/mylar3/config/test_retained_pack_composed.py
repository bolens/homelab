"""Real HTTP/native-worker factories; existing native host SDK/API-method adapters explicit."""
import hashlib
from http.server import BaseHTTPRequestHandler,HTTPServer
import json
import socket
import sqlite3
from contextlib import closing
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs
import test_retained_delivery_api as fixture

@unittest.skipUnless((Path(fixture.fixture.TOOL_ROOT)/'lib/archive_backend.py').is_file(),
                     'public archive backend required for retained pack controls')
class Composed(unittest.TestCase):
 def setUp(self):
  self.base=fixture.Endpoint('runTest');self.base.setUp();self.addCleanup(self.base.doCleanups)
  self.c=self.base.c.c;self.case=self.base.c.case;self.pack=self.base.c.store.get('pack',self.case.body['pack_id'])
  self.c.root.joinpath('config.ini').write_text('[General]\napi_key='+'x'*32+'\n')
  self.c.root.joinpath('config.ini').chmod(0o600)
  outer=self;self.requests=[]
  class HTTP(BaseHTTPRequestHandler):
   def do_POST(self):
    form=parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode(),strict_parsing=True)
    if set(form)!={'apikey','cmd','request'} or any(len(v)!=1 for v in form.values()):self.send_error(400);return
    outer.requests.append(form['cmd'][0]);h=outer.base.handler;h.cmd=form['cmd'][0];h.apikey=form['apikey'][0];h.kwargs={'request':form['request'][0]};h.data='OK'
    outer.base.http.request.method=self.command
    raw=h.fetchData().encode()
    if ((getattr(outer,'lose_reply',False) and h.cmd=='retainedDeliveryFinalize') or (getattr(outer,'lose_status',False) and h.cmd=='retainedDeliveryStatus')):self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
    self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
   def log_message(self,*args):pass
  self.server=HTTPServer(('127.0.0.1',0),HTTP);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.addCleanup(self.server.server_close);self.addCleanup(self.thread.join);self.addCleanup(self.server.shutdown)
 def plan(self):
  state=self.c.root/'worker-state';state.mkdir()
  completed=self.c.root/'completed';completed.mkdir()
  root=Path(__file__).parent;body=self.case.body
  return dict(pack_id=body['pack_id'],member_id=body['member_id'],source=str(self.case.original),target=str(self.case.target),capture_source=str(self.case.pack),
    owner=body['owner'],source_generation=body['source_generation'],worker_config=dict(state=str(state),roots=[str(self.case.case.library)],writer_state=str(self.c.writer_root),
    komga={'url':'http://127.0.0.1:1','api_key':'unused-fixture'},mylar={'url':'http://127.0.0.1:'+str(self.server.server_port),'config_dir':str(self.c.root)},
    publication_roots=[dict(native=str(self.case.case.library),worker=str(self.case.case.library))],maintenance=dict(completed=str(completed),ddl_cache=str(self.case.cache),mylar_ddl_cache=str(self.case.cache))),
    host_projection=dict(source_root=str(root),api_sha256=hashlib.sha256(root.joinpath('api.py').read_bytes()).hexdigest()))
 def execute(self,**extra):
  plan=self.plan();plan.update(extra)
  with tempfile.TemporaryDirectory() as tmp:
   inp=Path(tmp)/'plan.json';inp.write_text(json.dumps(plan));normalizer=Path(__file__).parent/'test_fixtures'/'retained_pack_worker'
   pins=json.loads((normalizer/'source-pins.json').read_bytes())
   self.assertEqual({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in normalizer.glob('*.py')},pins)
   result=subprocess.run([sys.executable,'-I','-B',str(normalizer/'check_retained_pack_composed_worker.py'),str(inp)],cwd=normalizer,capture_output=True,text=True,timeout=90)
   self.assertEqual(result.returncode,0,result.stderr)
   return json.loads(result.stdout)
 def test_genuine_factories_native_two_rows_and_worker_receipt_CAS_over_HTTP(self):
  answer=self.execute();self.assertTrue(answer['receipt_changed']);self.assertEqual(answer['member_phase'],'retained-accepted')
  self.assertFalse(answer['answer']['cleanup_grant']);self.assertEqual((answer['intent_count'],answer['done_count']),(1,1))
 def test_lost_HTTP_reply_retains_receipt_without_replay(self):
  self.lose_reply=True;answer=self.execute(expect_hold=True)
  self.assertTrue(answer['held']);self.assertFalse(answer['receipt_changed']);self.assertEqual(answer['done_count'],0)
  with closing(sqlite3.connect(self.c.database)) as db:self.assertEqual(len(db.execute("SELECT * FROM records WHERE kind='retained_delivery_final'").fetchall()),1)
 def test_capacity_refuses_before_native_workflow_commit(self):
  with sqlite3.connect(self.c.database) as db:db.execute("INSERT INTO records VALUES ('capacity','unrelated',?,0.0)",('\x7f'*800000,))
  answer=self.base.call();self.assertFalse(answer['success'])
  with closing(sqlite3.connect(self.c.database)) as db:self.assertEqual(len(db.execute("SELECT * FROM records WHERE kind='retained_delivery_final'").fetchall()),0)
 def test_original_serializer_replacement_after_source_capture_refuses(self):
  f=fixture.fixture.f;original=f.response_sources;old=self.base.api.Api._successResponse
  def changed():
   frame=original();self.base.api.Api._successResponse=lambda handler,value:old(handler,value);return frame
  try:
   with patch.object(f,'response_sources',changed):answer=self.base.call()
   self.assertFalse(answer['success'])
   with closing(sqlite3.connect(self.c.database)) as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM records WHERE kind='retained_delivery_final'").fetchone(),(0,))
  finally:self.base.api.Api._successResponse=old
 def test_real_budget_serializer_return_late_control_holds_before_SQL(self):
  fired=[]
  def profile(frame,event,arg):
   if event=='return' and frame.f_code.co_name=='_successResponse' and frame.f_back.f_code.co_name=='_precommit_response_budget':
    fired.append(True);self.c.native_database.chmod(0o640)
  try:
   sys.setprofile(profile);answer=self.base.call()
  finally:sys.setprofile(None)
  self.assertEqual(fired,[True]);self.assertFalse(answer['success'])
  with closing(sqlite3.connect(self.c.database)) as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM records WHERE kind='retained_delivery_final'").fetchone(),(0,))
 def test_non_ASCII_full_workflow_rows_preserved(self):
  with sqlite3.connect(self.c.database) as db:db.execute("INSERT INTO records VALUES ('unicode','unrelated',?,0.0)",('é漢字𝄞',))
  pack=self.base.c.store.get('pack',self.case.body['pack_id']);pack['opaque_title']='é漢字𝄞';self.base.c.store.set('pack',self.case.body['pack_id'],pack)
  answer=self.execute();self.assertEqual(answer['member_phase'],'retained-accepted')
  with closing(sqlite3.connect(self.c.database)) as db:self.assertEqual(db.execute("SELECT value FROM records WHERE kind='unicode'").fetchall(),[('é漢字𝄞',)])
 def test_annual_distinct_release_original_SQL_identity(self):
  with sqlite3.connect(self.c.native_database) as db:
   db.execute('DELETE FROM issues');db.execute('INSERT INTO annuals VALUES(?,?,?,?,?,?)',('123','456','789',self.case.target.name,'Archived',0))
  self.case.body['owner']={'table':'annuals','issueid':'123','parentcomicid':'456','releasecomicid':'789'}
  pack=self.base.c.store.get('pack',self.case.body['pack_id']);pack['members'][0].update(kind='annual',releasecomicid='789');self.base.c.store.set('pack',self.case.body['pack_id'],pack)
  answer=self.execute();self.assertEqual(answer['member_phase'],'retained-accepted')
  with closing(sqlite3.connect(self.c.native_database)) as db:self.assertEqual(db.execute('SELECT ReleaseComicID,Status FROM annuals').fetchall(),[('789','Archived')])
 def test_late_foreign_library_alias_refuses_receipt_CAS(self):self.refuses('claim')
 def test_late_control_refuses_receipt_CAS(self):self.refuses('control')
 def test_late_source_refuses_receipt_CAS(self):self.refuses('source')
 def test_late_receipt_refuses_receipt_CAS(self):self.refuses('receipt')
 def test_late_SQL_refuses_receipt_CAS(self):self.refuses('SQL')
 def refuses(self,fault):
  answer=self.execute(fault=fault,expect_hold=True)
  self.assertTrue(answer['held']);self.assertFalse(answer['receipt_changed']);self.assertEqual(answer['done_count'],0)
 def test_late_mapping_original_binding_refuses(self):
  answer=self.execute(fault='mapping',expect_hold=True)
  self.assertTrue(answer.get('held'),answer)

 def test_final_physical_callback_mapping_refuses_ACK(self):
  answer=self.execute(fault='final_mapping',expect_hold=True);self.assertTrue(answer['fired']);self.assertTrue(answer['held'])
  self.assertIn('retained-final-Maintenance',answer['error'])
 def test_final_physical_callback_writer_config_refuses_ACK(self):
  answer=self.execute(fault='final_writer_config',expect_hold=True);self.assertTrue(answer['fired']);self.assertTrue(answer['held'])
  self.assertIn('retained-final-Maintenance',answer['error'])
 def test_final_physical_callback_transport_refuses_ACK(self):
  answer=self.execute(fault='final_transport',expect_hold=True);self.assertTrue(answer['fired']);self.assertTrue(answer['held'])
  self.assertIn('retained-final-transport',answer['error'])

 def test_operations_real_selected_execution_UI_false_rights(self):
  result=self.execute(operations=True);self.assertEqual(result['answer']['retained_observed_members'],1)
  self.assertEqual(result['answer']['imported_members'],0);self.assertFalse(result['answer']['cleanup_grant'])
  self.assertEqual(self.requests,['retainedDeliveryFinalize'])
 def test_operations_lost_reply_status_CAS_once_no_finalize_replay(self):
  self.lose_reply=True;result=self.execute(operations=True,recover=True)
  self.assertTrue(result['lost']);self.assertEqual(result['original_view']['review_members'],1)
  self.assertEqual(result['answer']['retained_observed_members'],1);self.assertEqual(result['done_count'],1)
  self.assertEqual(self.requests,['retainedDeliveryFinalize','retainedDeliveryStatus'])
 def test_operations_lost_status_keeps_original_review_no_replay(self):
  self.lose_reply=True;self.lose_status=True;result=self.execute(operations=True,recover=True,expect_hold=True)
  self.assertTrue(result['held']);self.assertFalse(result['receipt_changed']);self.assertEqual(result['done_count'],0)
  self.assertEqual(result['view']['review_members'],1);self.assertTrue(result['view']['uncertain'])
  self.assertEqual(self.requests,['retainedDeliveryFinalize','retainedDeliveryStatus'])
 def test_operations_late_receipt_refuses_status_CAS(self):
  self.lose_reply=True;result=self.execute(operations=True,recover=True,status_fault='receipt',expect_hold=True)
  self.assertTrue(result['held']);self.assertFalse(result['receipt_changed']);self.assertEqual(result['done_count'],0)
  self.assertEqual(self.requests,['retainedDeliveryFinalize'])
 def test_operations_late_mapping_refuses_status_CAS(self):
  self.lose_reply=True;result=self.execute(operations=True,recover=True,status_fault='mapping',expect_hold=True)
  self.assertTrue(result['held']);self.assertFalse(result['receipt_changed']);self.assertEqual(result['done_count'],0)
  self.assertEqual(self.requests,['retainedDeliveryFinalize'])
 def test_operations_foreign_SQL_refuses_status_CAS(self):
  self.lose_reply=True;result=self.execute(operations=True,recover=True,status_fault='SQL',expect_hold=True)
  self.assertTrue(result['held']);self.assertFalse(result['receipt_changed']);self.assertEqual(result['done_count'],0)
  self.assertEqual(self.requests,['retainedDeliveryFinalize','retainedDeliveryStatus'])
 def test_operations_actual_fork_cannot_reconcile_original(self):
  self.lose_reply=True;result=self.execute(operations=True,recover=True,fork=True)
  self.assertEqual(result['answer']['retained_observed_members'],1)
  self.assertEqual(self.requests,['retainedDeliveryFinalize','retainedDeliveryStatus'])

 def test_operations_initializer_created_FD_mode_drift_refuses_before_proof(self):
  result=self.execute(operations=True,init_fault=True)
  self.assertTrue(result['fired']);self.assertTrue(result['held']);self.assertEqual(self.requests,[])
  self.assertIn('retained-init-original',result['error'])
 def test_operations_nested_initialization_does_not_supply_new_session(self):
  result=self.execute(operations=True,nested_init=True);self.assertEqual(result['answer']['retained_observed_members'],1)
 def test_operations_changed_SQL_mode_refuses_status_before_HTTP(self):
  self.lose_reply=True;result=self.execute(operations=True,recover=True,status_fault='SQL_mode',expect_hold=True)
  self.assertTrue(result['held']);self.assertFalse(result['receipt_changed']);self.assertEqual(self.requests,['retainedDeliveryFinalize'])

 def test_operations_original_initialized_directory_not_refreshed_before_proof(self):
  result=self.execute(operations=True,init_after=True,expect_hold=True)
  self.assertTrue(result['held']);self.assertFalse(result['receipt_changed']);self.assertEqual(self.requests,[])

 def test_operations_existing_original_journal_before_first_admission(self):
  result=self.execute(operations=True,init_existing=True,init_early='mode')
  self.assertTrue(result['fired']);self.assertTrue(result['held']);self.assertEqual(self.requests,[])
  self.assertIn('retained-init-original',result['error'])
 def test_operations_existing_journal_replacement_before_first_admission(self):
  result=self.execute(operations=True,init_existing=True,init_early='replace')
  self.assertTrue(result['fired']);self.assertTrue(result['held']);self.assertEqual(self.requests,[])
  self.assertIn('retained-init-original',result['error'])
 def test_operations_missing_journal_foreign_creation_before_first_admission(self):
  result=self.execute(operations=True,init_early='create')
  self.assertTrue(result['fired']);self.assertTrue(result['held']);self.assertEqual(self.requests,[])
  self.assertIn('retained-init-original-absence',result['error'])
 def test_operations_unchanged_existing_journal_positive(self):
  result=self.execute(operations=True,init_existing=True)
  self.assertEqual(result['answer']['retained_observed_members'],1)
  self.assertFalse(result['answer']['cleanup_grant'])

if __name__=='__main__':unittest.main()
