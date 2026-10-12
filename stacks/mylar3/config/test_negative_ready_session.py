"""Owning negative caller+real pipe/Writer/SQLite; downstream SDK factories projected.
No configured negative aggregate, installed-origin, NFS or live acceptance claim.
"""
from pathlib import Path
import sys
import types
import unittest
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'reader_recovery'))
import test_ready_writer_session as connected
import test_negative_reader_action as orchestration

class Negative(unittest.TestCase):
 def setUp(self):
  self.b=connected.Connected('runTest');self.b.setUp();self.addCleanup(lambda:(self.b.tearDown(),self.b.doCleanups()))
  self.a=orchestration.Tests('runTest');self.a.setUp();self.addCleanup(self.a.doCleanups)
  self.a.plan.update(provider_input=self.b.f.c.input,nonce=self.b.f.c.nonce,parent_sha256=self.b.f.c.parent['sha256'])
  self.a.modules['publication_reader_admission'].PARENT_SHA=self.a.plan['parent_sha256']
  self.b.parent.plan.update(version=9,kind='reviewed-negative-five-lifecycle-protocol')
  original=connected.fixtures.m.from_checked_parent
  def factory(lifecycle):
   self.assertIs(lifecycle,self.b.f.custody);self.scope=original(lifecycle);return self.scope
  self.a.modules['publication_native_configured_scope']=types.SimpleNamespace(NativeConfiguredScope=connected.fixtures.m.NativeConfiguredScope,from_checked_parent=factory)
  real_prep=self.a.modules['publication_negative'].prepare_existing
  def prep(*args):
   before=len(self.b.remote);self.scope.revalidate();self.b.callback(None)
   self.assertEqual(len(self.b.remote),before);self.assertGreater(args[1].local[1].depth,0)
   return real_prep(*args)
  self.a.modules['publication_negative'].prepare_existing=prep
  self.a.modules['publication_reader_native_coordinator'].from_held_existing=lambda c,w:self.a.coordinator
 def phase(self,value):
  # Exact compiled owning callback, with its actual phase argument fixture-bound.
  cells=dict(zip(self.b.callback.__code__.co_freevars,self.b.callback.__closure__))
  cells['phase'].cell_contents=value
 def run_purpose(self,execute=False):
  return orchestration.m.purpose_existing(self.a.plan,self.b.f.custody,self.a.modules,execute=execute)
 def test_prepare_actual_caller_no_remote_inside_real_writer(self):
  self.phase('prepare');before=self.b.guard.registry_snapshot(self.b.store.path,self.b.writer.root/'publication-v1.json')
  result=self.run_purpose();self.assertFalse(result['publication_acceptance']);self.assertNotIn('batch-marker',self.a.events)
  self.assertEqual(self.b.guard.registry_snapshot(self.b.store.path,self.b.writer.root/'publication-v1.json'),before)
  self.assertFalse(self.b.errors);self.assertNotIn(self.b.f.custody,connected.fixtures.l._WRITER_PIPE)
 def test_execute_actual_caller_preserves_original_ledger_and_terminal_boundary(self):
  self.phase('execute');before=self.b.guard.registry_snapshot(self.b.store.path,self.b.writer.root/'publication-v1.json')
  result=self.run_purpose(True);self.assertFalse(result['publication_acceptance']);self.assertFalse(result['reader_resume_authority'])
  self.assertIn('coordinator-terminal',self.a.events);self.assertEqual(self.b.guard.registry_snapshot(self.b.store.path,self.b.writer.root/'publication-v1.json'),before);self.assertFalse(self.b.errors)
 def test_negative_backup_cannot_announce_writer(self):
  self.phase('backup')
  with self.assertRaises(connected.fixtures.l.Held):self.run_purpose()
  self.assertNotIn('batch-marker',self.a.events)
 def test_negative_verify_terminal_cannot_announce_writer(self):
  self.phase('verify-terminal')
  with self.assertRaises(connected.fixtures.l.Held):self.run_purpose()
 def test_unreviewed_plan_version_cannot_announce_writer(self):
  self.phase('prepare');self.b.parent.plan['version']=8
  with self.assertRaises(connected.fixtures.l.Held):self.run_purpose()
 def test_foreign_negative_plan_kind_cannot_announce_writer(self):
  self.phase('prepare');self.b.parent.plan['kind']='foreign-negative'
  with self.assertRaises(connected.fixtures.l.Held):self.run_purpose()
 def test_original_census_drift_before_enter_refuses_no_work(self):
  import sqlite3,json
  self.phase('prepare')
  with sqlite3.connect(self.b.store.path) as db:
   key,raw=db.execute("SELECT key,value FROM records WHERE kind='publication_census'").fetchone();value=json.loads(raw);value['epoch']='f'*64
   db.execute("UPDATE records SET value=? WHERE kind='publication_census' AND key=?",(json.dumps(value),key));db.commit()
  with self.assertRaises((self.b.guard.Unavailable,connected.fixtures.m.Held,connected.fixtures.l.Held)):self.run_purpose()
  self.assertNotIn('batch-marker',self.a.events)
 def test_lost_enter_response_has_no_negative_work(self):
  self.phase('prepare');self.b.drop_stage='enter'
  with self.assertRaises((connected.fixtures.m.Held,connected.fixtures.l.Held)):self.run_purpose()
  self.assertNotIn('batch-marker',self.a.events)
 def test_lost_leave_response_has_no_report_ACK_or_replay(self):
  self.phase('prepare');self.b.drop_stage='leave'
  with self.assertRaises((connected.fixtures.m.Held,connected.fixtures.l.Held)):self.run_purpose()
  self.assertIn(self.b.f.custody,connected.fixtures.l._WRITER_PIPE);self.assertIsNone(self.b.seen_ack)

if __name__=='__main__':unittest.main()
