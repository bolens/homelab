"""Real disposable SQLite/FS mechanics; SDK/lifecycle terminals explicit doubles."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
p=load('provider_successor',str(Path(__file__).resolve().parent / 'comic_negative_reader_action.py'))
a=load('owning_aggregate',str(Path(__file__).resolve().parent / '_negative_reader_fixtures/fixture_publication_negative_aggregate_v5.py'))
f=load('real_sql_fixtures',str(Path(__file__).resolve().parent / '_negative_reader_fixtures/fixture_test_publication_reader_sql_commit_v4.py'))

class Controls(unittest.TestCase):
 def setUp(self):
  self.c=f.Tests();self.c.setUp();self.addCleanup(self.c.doCleanups)
  self.r=self.c.batch;self.r.core='a'*64;self.events=[]
  self.root=self.c.c.c.root;self.sources=self.root/'sources';self.targets=self.root/'targets';self.sources.mkdir();self.targets.mkdir()
  self.source=[self.sources/str(i) for i in range(5)];self.target=[self.targets/str(i) for i in range(5)]
  for i,source in enumerate(self.source):source.write_bytes(bytes([i])*16);source.chmod(0o600)
  self.original=[source.read_bytes() for source in self.source]
  self.marker=self.root/'fixture-marker';self.fail_stage=None;self.fail_consume=None
  outer=self
  class Prep:
   def __init__(s,i):s.i=i
   def consume(s,reservation):
    outer.events.append(('consume',s.i))
    if outer.fail_consume==s.i:raise RuntimeError('fixture-forward-fault')
    outer.source[s.i].unlink()
  preps=tuple(Prep(i) for i in range(5));self.r.batch.preparations=preps;self.c.reader.preparations=preps
  def stage():
   self.marker.write_bytes(b'owning fixture hold')
   for i in range(5):
    self.target[i].hardlink_to(self.source[i]);self.events.append(('link',i))
    if self.fail_stage==i:raise RuntimeError('fixture-link-fault')
  def restore():
   self.events.append('restore-native')
   for source,target in zip(self.source,self.target):
    if target.exists():
     if not source.exists():source.hardlink_to(target)
     target.unlink()
  self.r.stage_all=stage;self.r.rollback_staging=restore
  self.c.reader.accept_uncommitted_rollback=lambda sql,reservation:self.events.append('reader-original')
  self.start=SimpleNamespace(sql=self.c.sql,open_pending=lambda:None,close_pending=self.c.sql.close_pending)
  class Terminal:
   def __init__(s,rollback):s.rollback=rollback
   def clear(s):outer.events.append('rollback-clear' if s.rollback else 'forward-clear');outer.marker.unlink();return s.status()
   def status(s):return dict(marker_cleared=not outer.marker.exists(),publication_acceptance=False,rollback_verified=s.rollback,reader_before_verified=s.rollback,restored_count=5)
  self.modules=[SimpleNamespace(NegativeBatchReservation=type(self.r)),SimpleNamespace(prepare_existing=lambda *args:self.start),SimpleNamespace(ReaderSQLCommit=f.m.ReaderSQLCommit,from_pending=lambda *args:self.c.make()),SimpleNamespace(from_retired=lambda *args:Terminal(False)),SimpleNamespace(from_original=lambda *args:Terminal(True),from_reversed=lambda *args:Terminal(True))]
  self.aggregate=a.NegativeReaderAggregate(a._KEY,self.r,self.root/'start',self.c.journal,self.modules)
  self.provider_modules={'publication_negative_aggregate':a,'publication_reader_sql_commit':f.m}
 def go(self):return p.execute_or_rollback(self.aggregate,self.provider_modules)
 def original_restored(self):
  self.assertEqual([v.read_bytes() for v in self.source],self.original)
  self.assertFalse(any(v.exists() for v in self.target));self.assertFalse(self.marker.exists())
  self.assertEqual(self.c.sql.logical(),self.c.c.before)
 def test_partial_native_retirement_reverseSQL_and_restore(self):
  self.fail_consume=2;kind,status=self.go();self.assertEqual(kind,'negative-five-owning-rollback-observation');self.assertTrue(status['rollback_verified']);self.original_restored();self.assertEqual(self.aggregate.phase,'rollback-terminal')
 def test_partial_staging_restores_uncommitted_five(self):
  # SQLite effects here precede aggregate only as explicit fixture setup; real
  # provider stages before SQL. Roll back fixture setup to original first.
  self.c.sql.connection.rollback();self.fail_stage=2
  kind,status=self.go();self.assertTrue(status['rollback_verified']);self.assertEqual(kind,'negative-five-owning-rollback-observation');self.original_restored()
 def test_full_forward_remains_same_typed_terminal(self):
  kind,status=self.go();self.assertEqual(kind,'negative-five-owning-terminal-observation');self.assertFalse(status['rollback_verified']);self.assertFalse(any(v.exists() for v in self.source));self.assertTrue(all(v.exists() for v in self.target));self.assertEqual(self.c.sql.logical(),self.c.c.after)
 def test_lost_COMMIT_capture_no_reverse_or_terminal(self):
  with patch.object(f.m.ReaderSQLCommit,'_capture',side_effect=RuntimeError('fixture-lost-after-COMMIT')):
   with self.assertRaisesRegex(p.Held,'COMMIT-or-close-uncertain'):self.go()
  self.assertEqual(self.aggregate.sql_commit.phase,'commit-uncertain');self.assertEqual(self.c.sql.logical(),self.c.c.after);self.assertTrue(self.marker.exists());self.assertNotIn('restore-native',self.events)
 def test_native_failure_foreign_reader_delta_not_overwritten(self):
  def foreign(reservation):
   self.c.sql.connection.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='correct-0'");self.c.sql.connection.commit();raise RuntimeError('fixture-foreign')
  self.r.batch.preparations[0].consume=foreign
  with self.assertRaisesRegex(p.Held,'rollback-held'):self.go()
  self.assertEqual(self.c.sql.connection.execute("SELECT NAME FROM BOOK WHERE ID='correct-0'").fetchone()[0],'foreign');self.assertTrue(self.marker.exists());self.assertNotIn('restore-native',self.events)
 def test_reverse_receipt_loss_retains_hold_no_restore(self):
  self.fail_consume=0;real=f.m.ReaderSQLCommit._capture
  def capture(commit,expected):
   if commit.phase=='reverse-uncertain':raise RuntimeError('fixture-reverse-lost')
   return real(commit,expected)
  with patch.object(f.m.ReaderSQLCommit,'_capture',new=capture):
   with self.assertRaisesRegex(p.Held,'rollback-held'):self.go()
  self.assertTrue(self.marker.exists());self.assertNotIn('restore-native',self.events)
 def test_unknown_staging_ACK_foreign_source_preserved(self):
  # The actual aggregate owns rollback checks; fixture boundary demonstrates
  # a refusing typed restoration is not converted to an acknowledgement.
  self.fail_stage=1
  self.r.rollback_staging=lambda:(_ for _ in ()).throw(a.Held('fixture-current-custody-refused'))
  with self.assertRaisesRegex(p.Held,'rollback-held'):self.go()
  self.assertTrue(self.marker.exists());self.assertFalse(any(e=='rollback-clear' for e in self.events))
 def test_pending_factory_fault_rolls_back_actual_uncommitted_SQL(self):
  self.modules[2].from_pending=lambda *args:(_ for _ in ()).throw(a.Held('fixture-factory-fault'))
  kind,status=self.go();self.assertEqual(kind,'negative-five-owning-rollback-observation');self.assertTrue(status['rollback_verified']);self.original_restored();self.assertFalse(self.c.sql.connection.in_transaction)
 def test_process_interrupt_no_automatic_replay_or_clear(self):
  def interrupted():
   self.marker.write_bytes(b'fixture-hold');self.target[0].hardlink_to(self.source[0]);raise KeyboardInterrupt()
  self.r.stage_all=interrupted
  with self.assertRaises(KeyboardInterrupt):self.go()
  self.assertTrue(self.marker.exists());self.assertTrue(self.target[0].exists());self.assertNotIn('restore-native',self.events)
 def test_forged_aggregate_JSON_refused(self):
  with self.assertRaisesRegex(p.Held,'exact-owning-aggregate'):p.execute_or_rollback({'phase':'SQL-committed'},self.provider_modules)
 def test_no_replay_after_verified_rollback(self):
  self.fail_consume=1;self.go()
  with self.assertRaisesRegex(p.Held,'forward-uncertain'):self.go()
  self.original_restored()
 def test_mutated_aggregate_seal_no_rollback(self):
  self.aggregate.phase='SQL-committed'
  with self.assertRaises(a.Held):self.go()
  self.assertNotIn('restore-native',self.events)

class WALClosed(unittest.TestCase):
 def test_real_closed_WAL_not_reversed(self):
  c=f.WALTests();c.setUp();self.addCleanup(c.doCleanups)
  x=c.make();x.commit();c.owned_close(x)
  r=c.batch;r.core='b'*64
  modules=[SimpleNamespace(NegativeBatchReservation=type(r)),SimpleNamespace(prepare_existing=lambda *args:c.start),SimpleNamespace(ReaderSQLCommit=f.m.ReaderSQLCommit,from_pending=f.m.from_pending),SimpleNamespace(from_retired=lambda *args:None),SimpleNamespace(from_original=lambda *args:None,from_reversed=lambda *args:None)]
  aggregate=a.NegativeReaderAggregate(a._KEY,r,Path(__file__).resolve().parent/'_unused_start',Path(__file__).resolve().parent/'_unused_commit',modules)
  aggregate.start=c.start;aggregate.sql_commit=x;aggregate.phase='sources-retained';aggregate._seal()
  with patch.object(a.NegativeReaderAggregate,'execute',side_effect=a.Held('fixture-after-close')):
   with self.assertRaisesRegex(p.Held,'COMMIT-or-close-uncertain'):p.execute_or_rollback(aggregate,{'publication_negative_aggregate':a,'publication_reader_sql_commit':f.m})
  self.assertTrue(x.closed);self.assertEqual(x.phase,'committed')

if __name__=='__main__':unittest.main()
