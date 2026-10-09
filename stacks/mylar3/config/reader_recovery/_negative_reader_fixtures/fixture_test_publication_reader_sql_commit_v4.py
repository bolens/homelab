"""Real temporary SQLite commit/reverse; EXPLICIT fake typed handshake only.

These fixtures prove mechanics, not installed factories, stopped service or
native/reader authority. The public factory must refuse this fixture package.
"""
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import patch

def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load('reader_commit',str(Path(__file__).resolve().parent / 'fixture_publication_reader_sql_commit_v4.py'))
f=load('custody_fixture',str(Path(__file__).resolve().parent / 'fixture_test_publication_reader_sql_custody_v5.py'))
class Tests(unittest.TestCase):
 def setUp(self):
  self.c=f.Tests();self.c.setUp();self.addCleanup(self.c.doCleanups)
  self.sql=self.c.make();self.sql.apply_body(f.r.sql_five_transition)
  self.journal=self.c.c.root/'commit-journal';self.journal.mkdir(mode=0o700)
  class Reader:
   def revalidate_sql_writing(r,s,b):s.close_pending()
   def sql_syscall_controls(r,s,b):return {},{},()
   def accept_committed(r,c):r.custody=c
   def revalidate_sql_observed(r,c,b):pass
   def sql_observed_controls(r,c,b):return {},{},()
   def revalidate_sql_reversing(r,c,s,b):s.close_pending()
   def sql_reverse_controls(r,c,s,b):return {},{},()
   def accept_reversed(r,c):r.custody=c
  class Batch:
   def close_native_precommit(b,r):pass
   def native_sql_controls(b,r):return {},{},()
   def close_native_reverse(b,r):pass
  self.reader=Reader();self.batch=Batch();self.reader.sql=self.sql;self.reader.batch=self.batch;self.batch.reader=self.reader
  self.reader.preparations=tuple(object() for _ in range(5));self.batch.batch=types.SimpleNamespace(preparations=self.reader.preparations)
  self.reader.tasks_database=self.c.c.config/'tasks.sqlite';self.reader.tasks_pair=f.m.raw_pair(self.reader.tasks_database)
  self.reader.sql_operation=self.journal
  self.reader.scratch=self.c.c.scratch
  self.modules=(f.m,types.SimpleNamespace(StoppedReaderPhase=Reader),types.SimpleNamespace(NegativeBatchReservation=Batch),f.r)
 def make(self):return m.ReaderSQLCommit(m._KEY,self.sql,self.reader,self.batch,self.modules)
 def test_real_commit_exact_five_and_all_tables(self):
  x=self.make();self.assertIs(x.commit(),x);self.assertFalse(self.c.conn.in_transaction);self.assertEqual(self.sql.logical(),self.c.after);x.close_committed(self.batch)
  self.assertEqual(x.binding['phase'],'committed');self.assertFalse(x.binding['publication_acceptance']);self.assertFalse(x.binding['mutation_authority'])
 def test_real_reverse_exact_five_and_all_tables(self):
  x=self.make();x.commit();x.reverse();self.assertEqual(self.sql.logical(),self.c.before);x.close_reversed(self.batch)
  self.assertFalse(self.c.conn.in_transaction);self.assertEqual(x.binding['phase'],'reversed')
 def test_tasks_bytes_attrs_never_change(self):
  before=f.m.raw_pair(self.reader.tasks_database);x=self.make();x.commit();x.reverse();self.assertEqual(f.m.raw_pair(self.reader.tasks_database),before)
 def test_public_factory_has_no_fixture_grant(self):
  with self.assertRaises(m.Held):m.from_pending(self.sql,self.reader,self.batch)
 def test_boolean_key_refuses(self):
  with self.assertRaises(m.Held):m.ReaderSQLCommit(True,self.sql,self.reader,self.batch,self.modules)
 def test_wrong_reservation_refuses(self):
  x=self.make();x.commit()
  with self.assertRaises(m.Held):x.close_committed(object())
 def test_foreign_main_mode_before_commit_retains_intent(self):
  x=self.make();self.c.db.chmod(0o640)
  with self.assertRaises(ValueError):x.commit()
  self.assertTrue(self.c.conn.in_transaction);self.assertEqual(list(self.journal.iterdir()),[])
 def test_native_last_callback_main_mode_refuses_before_commit(self):
  x=self.make();self.batch.native_sql_controls=lambda r:(self.c.db.chmod(0o640) or ({},{},()))
  with self.assertRaises(ValueError):x.commit()
  self.assertTrue(self.c.conn.in_transaction)
 def test_late_intent_write_mode_refuses_before_commit(self):
  x=self.make();real=x._record
  def changed(name):real(name);self.c.db.chmod(0o640)
  with patch.object(x,'_record',side_effect=changed):
   with self.assertRaises(ValueError):x.commit()
  self.assertTrue(self.c.conn.in_transaction);self.assertTrue((self.journal/'commit-intent.json').exists())
 def test_no_commit_replay(self):
  x=self.make();x.commit()
  with self.assertRaises(m.Held):x.commit()
 def test_committed_pair_samebytes_inode_replacement_held(self):
  x=self.make();x.commit();data=self.c.db.read_bytes();self.c.db.rename(self.c.db.with_suffix('.retained'));self.c.db.write_bytes(data)
  with self.assertRaises(m.Held):x.close_committed(self.batch)
 def test_committed_unrelated_row_mutation_held(self):
  x=self.make();x.commit();self.c.conn.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='correct-0'");self.c.conn.commit()
  with self.assertRaises(m.Held):x.close_committed(self.batch)
 def test_last_reader_callback_catalog_tasks_change_held(self):
  x=self.make();x.commit();self.reader.sql_observed_controls=lambda *a:(self.reader.tasks_database.chmod(0o640) or ({},{},()))
  with self.assertRaises(m.Held):x.close_committed(self.batch)
 def test_late_reader_callback_foreign_journal_held(self):
  x=self.make();x.commit();self.reader.sql_observed_controls=lambda *a:((self.journal/'foreign').write_bytes(b'foreign') and ({},{},()))
  with self.assertRaises(m.Held):x.close_committed(self.batch)
 def test_receipt_rewrite_no_ack(self):
  x=self.make();x.commit();(self.journal/'committed.json').write_bytes(b'{}')
  with self.assertRaises(m.Held):x.close_committed(self.batch)
 def test_commit_receipt_identity_and_five_ids_bound(self):
  x=self.make();x.commit();b=x.binding;self.assertEqual(len(b['preparation_ids']),5);self.assertEqual(b['reservation_id'],id(self.batch));self.assertEqual(b['receipt']['path'],str(self.journal/'committed.json'))
 def test_copy_binding_cannot_reseal(self):
  x=self.make();x.commit();b=x.binding;b['main_pair']={};x.close_committed(self.batch)
 def test_reverse_foreign_current_row_never_changes_back(self):
  x=self.make();x.commit();self.c.conn.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='wrong-0'");self.c.conn.commit()
  with self.assertRaises(m.Held):x.reverse()
  self.assertEqual(self.c.conn.execute("SELECT NAME FROM BOOK WHERE ID='wrong-0'").fetchone()[0],'foreign')
 def test_reverse_late_native_callback_mode_refuses(self):
  x=self.make();x.commit();self.batch.close_native_reverse=lambda r:self.c.db.chmod(0o640)
  with self.assertRaises(m.Held):x.reverse()
  self.assertFalse(self.c.conn.in_transaction)
 def test_clear_marker_does_not_break_reader_only_proof(self):
  x=self.make();x.commit();self.batch.close_native_precommit=lambda r:(_ for _ in ()).throw(AssertionError('native callback forbidden'));x.close_committed(self.batch)
 def test_unknown_commit_response_retained_no_replay(self):
  x=self.make()
  with patch.object(x,'_capture',side_effect=RuntimeError('lost response after actual commit')):
   with self.assertRaises(RuntimeError):x.commit()
  self.assertFalse(self.c.conn.in_transaction);self.assertEqual(self.sql.logical(),self.c.after);self.assertEqual(x.binding['phase'],'commit-uncertain')
  self.assertTrue((self.journal/'commit-intent.json').exists());self.assertFalse((self.journal/'committed.json').exists())
  with self.assertRaises(m.Held):x.commit()
 def test_unknown_reverse_response_retained_no_replay(self):
  x=self.make();x.commit()
  with patch.object(x,'_capture',side_effect=RuntimeError('lost reversal ACK')):
   with self.assertRaises(RuntimeError):x.reverse()
  self.assertEqual(self.sql.logical(),self.c.before);self.assertEqual(x.binding['phase'],'reverse-uncertain');self.assertTrue((self.journal/'reverse-intent.json').exists())
  with self.assertRaises(m.Held):x.reverse()
 def test_current_pair_and_state_reseal_cannot_mint_successor(self):
  x=self.make();x.commit();raw=self.c.db.read_bytes();self.c.db.rename(self.c.db.with_suffix('.retained'));self.c.db.write_bytes(raw);self.c.db.chmod(0o600)
  x.current=f.m.raw_pair(self.c.db);x.directory=m.sig(x.root);x.state=x._state()
  with self.assertRaises(m.Held):x.close_committed(self.batch)
 def test_intent_FD_parent_alias_never_writes_foreign(self):
  import os
  x=self.make();real=os.open;foreign=self.c.c.root/'foreign-journal';foreign.mkdir(mode=0o700);saved=self.c.c.root/'saved-journal';fired=False
  def raced(p,flags,*a,**kw):
   nonlocal fired
   if str(p)=='commit-intent.json' and kw.get('dir_fd') is not None and not fired:
    fired=True;self.journal.rename(saved);self.journal.symlink_to(foreign,target_is_directory=True)
    try:return real(p,flags,*a,**kw)
    finally:self.journal.unlink();saved.rename(self.journal)
   return real(p,flags,*a,**kw)
  with patch.object(m.os,'open',side_effect=raced):x.commit()
  self.assertTrue(fired);self.assertEqual(list(foreign.iterdir()),[]);self.assertTrue((self.journal/'committed.json').exists())
 def test_last_reader_observed_callback_companion_creation_held(self):
  x=self.make();x.commit()
  def late(*a):Path(str(self.c.db)+'-wal').write_bytes(b'foreign');return {},{}
  self.reader.sql_observed_controls=late
  with self.assertRaises(m.Held):x.close_committed(self.batch)
 def test_last_reader_callback_source_inode_change_held(self):
  x=self.make();x.commit()
  def late(*a):
   raw=self.c.db.read_bytes();self.c.db.rename(self.c.db.with_suffix('.retained'));self.c.db.write_bytes(raw);return {},{}
  self.reader.sql_observed_controls=late
  with self.assertRaises(m.Held):x.close_committed(self.batch)
 def test_tasks_samebytes_replacement_before_commit_no_commit(self):
  x=self.make();db=self.reader.tasks_database;raw=db.read_bytes();db.rename(db.with_suffix('.retained'));db.write_bytes(raw)
  with self.assertRaises(ValueError):x.commit()
  self.assertTrue(self.c.conn.in_transaction)
 def test_last_committed_receipt_write_main_drift_no_ACK(self):
  x=self.make();real=x._record
  def late(name):real(name);self.c.db.chmod(0o640) if name=='committed' else None
  with patch.object(x,'_record',side_effect=late):
   with self.assertRaises(m.Held):x.commit()
  self.assertFalse(self.c.conn.in_transaction);self.assertTrue((self.journal/'commit-intent.json').exists())
 def test_last_reversed_receipt_write_tasks_drift_no_ACK(self):
  x=self.make();x.commit();real=x._record
  def late(name):real(name);self.reader.tasks_database.chmod(0o640) if name=='reversed' else None
  with patch.object(x,'_record',side_effect=late):
   with self.assertRaises(m.Held):x.reverse()
  self.assertEqual(self.sql.logical(),self.c.before);self.assertTrue((self.journal/'reverse-intent.json').exists())
 def test_stale_native_binding_before_intent_no_COMMIT(self):
  x=self.make();self.batch.close_native_precommit=lambda r:(_ for _ in ()).throw(m.Held('stale-census'))
  with self.assertRaises(m.Held):x.commit()
  self.assertEqual(list(self.journal.iterdir()),[]);self.assertTrue(self.c.conn.in_transaction)
 def test_five_original_ids_in_immutable_core(self):
  x=self.make();x.preparation_ids=tuple(range(5));x.core=x._core();x.state=x._state()
  with self.assertRaises(m.Held):x.commit()
 def test_negative_claim_absent_ancestor_preserved(self):
  absent=self.c.c.root/'missing-parent';self.batch.native_sql_controls=lambda r:({},{absent:None})
  x=self.make();x.commit();files,nodes=x.vectors();self.assertIn(Path(str(self.c.db)+'-journal'),files);self.assertIsNone(files[Path(str(self.c.db)+'-journal')])
 def test_late_negative_claim_absent_ancestor_creation_refuses(self):
  absent=self.c.c.root/'missing-parent';x=self.make()
  def changed(r):absent.mkdir();return {},{absent:None}
  self.batch.native_sql_controls=changed
  with self.assertRaises(m.Held):x.commit()
  self.assertTrue(self.c.conn.in_transaction)
 def wal_pending(self):
  import sqlite3
  self.c.conn.rollback();self.c.conn.close()
  connection=sqlite3.connect(self.c.db);connection.execute('PRAGMA journal_mode=WAL');connection.close()
  self.c.conn=self.c.disk.connect(self.c.db);self.c.conn.execute('BEGIN IMMEDIATE')
  baseline=f.m.raw_pair(self.c.db)
  self.sql=f.m.SQLWritingCustody(f.m._KEY,self.c.conn,self.c.db,self.c.disk,self.c.c.plan,self.c.before,self.c.after,baseline)
  self.sql.apply_body(f.r.sql_five_transition);self.reader.sql=self.sql
 def test_real_WAL_mechanics_detached_observation_no_owning_grant(self):
  self.wal_pending();self.c.conn.commit();baseline=f.m.raw_pair(self.c.db)
  self.assertIn('-wal',baseline);self.assertIn('-shm',baseline)
  self.assertEqual(self.c.disk.observe_copy(self.c.db,self.c.c.plan,self.reader.scratch),self.c.after)
  self.assertEqual(f.m.raw_pair(self.c.db),baseline)
 def test_WAL_owning_factory_refuses_before_intent_or_commit(self):
  self.wal_pending();baseline=f.m.raw_pair(self.c.db)
  with self.assertRaisesRegex(m.Held,'WAL-COMMIT-needs-supported-reverse-phase'):self.make()
  self.assertEqual(f.m.raw_pair(self.c.db),baseline);self.assertTrue(self.c.conn.in_transaction)
  self.assertEqual(list(self.journal.iterdir()),[])
 def test_detached_observation_late_foreign_SQL_refuses(self):
  x=self.make();x.commit();real=self.c.disk.observe_copy
  def late(*args):
   result=real(*args);self.c.conn.execute("UPDATE BOOK SET NAME='foreign-late' WHERE ID='correct-0'");self.c.conn.commit();return result
  with patch.object(self.c.disk,'observe_copy',side_effect=late):
   with self.assertRaises(m.Held):x.close_committed(self.batch)
  self.assertEqual(self.c.conn.execute("SELECT NAME FROM BOOK WHERE ID='correct-0'").fetchone()[0],'foreign-late')
 def test_last_detached_observation_scratch_alias_refuses(self):
  x=self.make();x.commit();real=self.c.disk.observe_copy;scratch=self.reader.scratch;saved=scratch.with_name('scratch-saved')
  def late(*args):
   result=real(*args);scratch.rename(saved);scratch.symlink_to(saved,target_is_directory=True);return result
  with patch.object(self.c.disk,'observe_copy',side_effect=late):
   with self.assertRaises(m.Held):x.close_committed(self.batch)
 def test_literal_second_precommit_last_ancestor_helper_mode_no_COMMIT(self):
  x=self.make();real=m.s5;count=0;target=2*len(set(x.sql.nodes)|set(x.nodes));fired=[]
  def late(z):
   nonlocal count
   result=real(z);count+=1
   if count==target:self.c.db.chmod(0o640);fired.append(True)
   return result
  with patch.object(m,'s5',side_effect=late),self.assertRaises(m.Held):x.commit()
  self.assertTrue(fired);self.assertTrue(self.c.conn.in_transaction)
  self.assertEqual(x.phase,'commit-uncertain');self.assertFalse((self.journal/'committed.json').exists())
 def test_final_helper_missing_companion_creation_no_COMMIT(self):
  x=self.make();real=m.s5;count=0;target=len(set(x.sql.nodes)|set(x.nodes));fired=[]
  def late(z):
   nonlocal count
   result=real(z);count+=1
   if count==target:Path(str(self.c.db)+'-wal').write_bytes(b'foreign');fired.append(True)
   return result
  with patch.object(m,'s5',side_effect=late),self.assertRaises(m.Held):x.commit()
  self.assertTrue(fired);self.assertTrue(self.c.conn.in_transaction)
 def test_commit_uncertain_state_seal_callback_precedes_final_closure(self):
  x=self.make();real=x._state;fired=[]
  def late():
   result=real()
   if not fired and x.phase=='commit-uncertain':self.reader.tasks_database.chmod(0o640);fired.append(True)
   return result
  with patch.object(x,'_state',side_effect=late),self.assertRaises(ValueError):x.commit()
  self.assertTrue(fired);self.assertTrue(self.c.conn.in_transaction)
 def test_last_ancestor_helper_pre_reverse_BEGIN_no_SQL(self):
  x=self.make();x.commit();real=m.s5;count=0;target=len(set(x.sql.nodes)|set(x.nodes));fired=[]
  def late(z):
   nonlocal count
   result=real(z)
   if x.phase=='reverse-uncertain':
    count+=1
    if count==target:self.c.db.chmod(0o640);fired.append(True)
   return result
  with patch.object(m,'s5',side_effect=late),self.assertRaises(m.Held):x.reverse()
  self.assertTrue(fired);self.assertEqual(self.sql.logical(),self.c.after)
  self.assertFalse(self.c.conn.in_transaction);self.assertFalse((self.journal/'reversed.json').exists())
 def test_last_ancestor_helper_pre_reverse_COMMIT_rolls_back_pending_body(self):
  x=self.make();x.commit();real=m.s5;count=0;target=3*len(set(x.sql.nodes)|set(x.nodes));fired=[]
  def late(z):
   nonlocal count
   result=real(z)
   if x.phase=='reverse-uncertain':
    count+=1
    if count==target:self.reader.tasks_database.chmod(0o640);fired.append(True)
   return result
  with patch.object(m,'s5',side_effect=late),self.assertRaises(m.Held):x.reverse()
  self.assertTrue(fired);self.assertEqual(self.sql.logical(),self.c.after)
  self.assertFalse((self.journal/'reversed.json').exists())
 def test_last_helper_after_committed_file_checks_no_final_ACK(self):
  x=self.make();x.commit();real=m.s5;count=0;target=len(set(x.sql.nodes)|set(x.nodes));fired=[]
  def late(z):
   nonlocal count
   result=real(z);count+=1
   if count==target:self.reader.tasks_database.chmod(0o640);fired.append(True)
   return result
  with patch.object(m,'s5',side_effect=late),self.assertRaises(m.Held):x.close_committed(self.batch)
  self.assertTrue(fired)
 def test_last_helper_foreign_journal_child_no_COMMIT(self):
  x=self.make();real=m.s5;count=0;target=len(set(x.sql.nodes)|set(x.nodes));fired=[]
  def late(z):
   nonlocal count
   result=real(z);count+=1
   if count==target:(self.journal/'foreign').write_bytes(b'keep');fired.append(True)
   return result
  with patch.object(m,'s5',side_effect=late),self.assertRaises(m.Held):x.commit()
  self.assertTrue(fired);self.assertTrue(self.c.conn.in_transaction)
 def test_last_immutable_helper_cannot_rebase_admitted_ancestor_vector(self):
  import inspect
  x=self.make();real=x._life;fired=[];p=self.reader.scratch
  def late():
   result=real()
   if not fired and any(frame.function=='_direct' for frame in inspect.stack()):
    p.chmod(0o750)
    z=p.lstat();x.nodes[p][:]=[z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]
    fired.append(True)
   return result
  with patch.object(x,'_life',side_effect=late),self.assertRaises(m.Held):x.commit()
  self.assertTrue(fired);self.assertTrue(self.c.conn.in_transaction)


class WALTests(unittest.TestCase):
 def setUp(self):
  self.o=load('opening_fixture',str(Path(__file__).resolve().parent / 'fixture_test_publication_reader_sql_start_v4.py'))
  self.o.r=load('latest_reader',str(Path(__file__).resolve().parent / 'fixture_publication_reader_phase_v9.py'));self.o.f.m=self.o.r
  self.fixture=self.o.Tests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
  c=self.fixture;conn=c.reader.disk.connect(c.reader.root/'database.sqlite');conn.execute('PRAGMA journal_mode=WAL');conn.close()
  c.c.fixture.negative=[type(c.c.fixture.negative[0])(c.c.fixture.archive) for _ in range(5)]
  c.reader=self.o.r.StoppedReaderPhase(self.o.r._KEY,c.c.fixture.admission());c.batch.reader=c.reader;c.batch.batch.preparations=c.reader.preparations
  self.w=load('latest_wal',str(Path(__file__).resolve().parent / 'fixture_publication_reader_wal_phase_v5.py'))
  c.modules[0].sql_five_transition=self.o.r.sql_five_transition
  c.modules[2].raw_pair=self.o.sql.raw_pair;c.modules[2].from_wal_begin=self.o.sql.from_wal_begin
  c.map.update({'mylar.publication_reader_wal_phase':types.SimpleNamespace(__file__='/app/mylar3/mylar/publication_reader_wal_phase.py',WALReaderPhase=self.w.WALReaderPhase,from_opening=self.w.from_opening),
    'mylar.publication_reader_sql_start':types.SimpleNamespace(__file__='/app/mylar3/mylar/publication_reader_sql_start.py',ReaderSQLStart=self.o.m.ReaderSQLStart),
    'mylar.publication_reader_sql_commit':types.SimpleNamespace(__file__='/app/mylar3/mylar/publication_reader_sql_commit.py',ReaderSQLCommit=m.ReaderSQLCommit,from_pending_wal=m.from_pending_wal)})
  self.patch=patch.object(m.importlib,'import_module',side_effect=c.module);self.patch.start();self.addCleanup(self.patch.stop)
  self.start=c.make();self.start.open_pending();self.start.close_pending();self.addCleanup(self.start.sql.connection.close)
  self.reader=c.reader;self.batch=c.batch;self.sql=self.start.sql
  self.batch.close_native_reverse=lambda reader:None
  self.task_before=self.o.sql.raw_pair(self.reader.tasks_database)
  self.origin_pairs=__import__('copy').deepcopy(self.reader.original._pairs)
 def make(self):return m.from_pending_wal(self.sql,self.reader,self.batch,self.start.wal_phase)
 def owned_close(self,x):
  self.batch.projection=types.SimpleNamespace(phases=['retained']*5 if x.phase=='committed' else ['linked']*5)
  return x.close_owned_connection()
 def observe(self):return self.reader.disk.observe_copy(self.sql.db,self.reader.plan,self.reader.scratch)
 def test_WAL_early_forward_close_before_retirement_held(self):
  x=self.make();x.commit();self.batch.projection=types.SimpleNamespace(phases=['linked']*5)
  with self.assertRaisesRegex(m.Held,'native-phase-before-owned'):x.close_owned_connection()
  self.assertFalse((x.journal/'connection-close-intent.json').exists());self.assertFalse(x.closed)
  self.assertEqual(x.connection.execute('SELECT 1').fetchone(),(1,))
 def test_WAL_five_forward_commit_then_checkpoint_close(self):
  x=self.make();x.commit();self.assertEqual(self.observe(),self.reader.after['database.sqlite'])
  self.assertFalse(x.closed);self.assertIs(x.connection,self.start.wal_phase.connection)
  self.assertEqual(self.start.wal_phase.phase,'committed-open');self.owned_close(x)
  self.assertTrue(x.closed);self.assertEqual(set(x.current),{''});self.assertEqual(self.observe(),x.after)
  self.assertEqual(self.o.sql.raw_pair(x.tasks),self.task_before);self.assertEqual(self.reader.original._pairs,self.origin_pairs)
  x.close_committed(self.batch);self.assertFalse(x.binding['publication_acceptance'])
 def test_WAL_same_connection_five_reverse_then_close(self):
  x=self.make();connection=x.connection;x.commit();x.reverse();self.assertIs(x.connection,connection)
  self.assertEqual(self.observe(),x.before);self.assertEqual(x.phase,'reversed');self.assertFalse(x.closed)
  self.owned_close(x);x.close_reversed(self.batch)
  self.assertEqual(set(x.current),{''});self.assertEqual(self.o.sql.raw_pair(x.tasks),self.task_before)
  self.assertEqual(self.reader.original._pairs,self.origin_pairs)
 def test_WAL_nonowning_old_factory_still_holds(self):
  with self.assertRaisesRegex(m.Held,'WAL-COMMIT-needs'):m.from_pending(self.sql,self.reader,self.batch)
 def test_WAL_foreign_phase_before_any_COMMIT_receipt(self):
  with self.assertRaisesRegex(m.Held,'exact-owned-WAL'):m.from_pending_wal(self.sql,self.reader,self.batch,True)
  self.assertTrue(self.sql.connection.in_transaction);self.assertFalse(list(self.fixture.commit.iterdir()))
 def test_WAL_late_precommit_mode_no_COMMIT(self):
  x=self.make();real=x._record
  def changed(name):real(name);self.sql.db.chmod(0o640)
  with patch.object(x,'_record',side_effect=changed):
   with self.assertRaises(ValueError):x.commit()
  self.assertTrue(x.connection.in_transaction);self.assertEqual(self.observe(),x.before)
 def test_WAL_lost_forward_ACK_no_replay(self):
  x=self.make()
  with patch.object(x,'_capture',side_effect=RuntimeError('disposable lost ACK')):
   with self.assertRaises(RuntimeError):x.commit()
  self.assertEqual(x.phase,'commit-uncertain');self.assertEqual(self.observe(),x.after)
  with self.assertRaises(m.Held):x.commit()
  self.assertFalse(x.closed)
 def test_WAL_reverse_unrelated_row_change_not_overwritten(self):
  x=self.make();x.commit();x.connection.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='correct-0'");x.connection.commit()
  with self.assertRaises(ValueError):x.reverse()
  self.assertEqual(x.connection.execute("SELECT NAME FROM BOOK WHERE ID='correct-0'").fetchone()[0],'foreign')
 def test_WAL_last_reverse_native_callback_no_reverse_COMMIT(self):
  x=self.make();x.commit();real=self.batch.native_sql_controls;fired=[]
  def changed(reader):
   value=real(reader)
   if x.reverse_sql is not None and not fired:self.sql.db.chmod(0o640);fired.append(True)
   return value
  self.batch.native_sql_controls=changed
  with self.assertRaises(ValueError):x.reverse()
  self.assertTrue(fired);self.assertTrue(x.connection.in_transaction)
  self.assertEqual(self.observe(),x.after)
 def test_WAL_closed_connection_cannot_reverse_or_reclose(self):
  x=self.make();x.commit();self.owned_close(x)
  with self.assertRaisesRegex(m.Held,'owned-open-WAL'):x.reverse()
  with self.assertRaisesRegex(m.Held,'single-owned-WAL'):self.owned_close(x)
 def test_WAL_close_late_receipt_control_drift_no_ACK(self):
  x=self.make();x.commit();real=x._record
  def changed(name):
   real(name)
   if name=='connection-close-intent':self.reader.tasks_database.chmod(0o640)
  with patch.object(x,'_record',side_effect=changed):
   with self.assertRaises(ValueError):self.owned_close(x)
  self.assertFalse(x.closed);self.assertEqual(x.connection.execute('SELECT 1').fetchone(),(1,))
 def test_WAL_closed_pair_receipt_drift_retains_false_ACK(self):
  x=self.make();x.commit();real=x._record
  def changed(name):
   real(name)
   if name=='connection-closed':(x.journal/'connection-closed.json').write_bytes(b'{}')
  with patch.object(x,'_record',side_effect=changed):
   with self.assertRaises(ValueError):self.owned_close(x)
  self.assertTrue(x.closed);self.assertFalse(x.binding['publication_acceptance'])
 def test_WAL_opening_receipt_changed_before_factory_no_COMMIT(self):
  (self.start.journal/'opening.json').write_bytes(b'{}')
  with self.assertRaises(ValueError):self.make()
  self.assertTrue(self.sql.connection.in_transaction);self.assertFalse(list(self.fixture.commit.iterdir()))
 def test_WAL_late_opening_receipt_change_before_COMMIT_held(self):
  x=self.make();real=x._record
  def changed(name):
   real(name)
   if name=='commit-intent':(self.start.journal/'opening.json').write_bytes(b'{}')
  with patch.object(x,'_record',side_effect=changed):
   with self.assertRaises(ValueError):x.commit()
  self.assertTrue(x.connection.in_transaction)
 def test_WAL_opening_namespace_late_child_held_after_commit(self):
  x=self.make();x.commit();real=self.reader.sql_observed_controls
  def changed(*a):
   value=real(*a);(self.start.journal/'foreign').write_bytes(b'foreign');return value
  self.reader.sql_observed_controls=changed
  with self.assertRaises(ValueError):x.close_committed(self.batch)
  self.assertFalse(x.binding['publication_acceptance'])
 def test_WAL_last_forward_ancestor_helper_no_COMMIT(self):
  import inspect
  x=self.make();real=m.s5;calls=0;fired=[]
  def changed(z):
   nonlocal calls
   value=real(z)
   if inspect.currentframe().f_back.f_code.co_name=='_direct':calls+=1
   if calls==len(x.nodes)+1:self.sql.db.chmod(0o640);fired.append(True)
   return value
  with patch.object(m,'s5',new=changed):
   with self.assertRaises(ValueError):x.commit()
  self.assertTrue(fired);self.assertTrue(x.connection.in_transaction)
 def test_WAL_reverse_body_last_logical_callback_no_first_UPDATE(self):
  import inspect
  x=self.make();x.commit();real=self.sql.disk.book_rows;fired=[]
  def changed(conn,plan):
   value=real(conn,plan)
   if inspect.currentframe().f_back.f_code.co_name=='_wal_reverse_body' and not fired:
    self.reader.tasks_database.chmod(0o640);fired.append(True)
   return value
  with patch.object(self.sql.disk,'book_rows',new=changed):
   with self.assertRaises(ValueError):x.reverse()
  self.assertTrue(fired);self.assertTrue(x.connection.in_transaction)
  self.assertEqual(x.reverse_sql.logical(),x.after);self.assertEqual(self.observe(),x.after)
 def test_WAL_reverse_body_native_absent_claim_creation_no_UPDATE(self):
  x=self.make();x.commit();missing=self.fixture.c.fixture.root/'absent-native-claim';real=self.batch.native_sql_controls;fired=[]
  def changed(reader):
   value=real(reader)
   if x.reverse_sql is not None and not fired:missing.write_bytes(b'foreign');fired.append(True)
   return {missing:None},value[1]
  self.batch.native_sql_controls=changed
  with self.assertRaises(ValueError):x.reverse()
  self.assertTrue(fired);self.assertEqual(x.reverse_sql.logical(),x.after)
 def test_WAL_lost_reverse_ACK_no_replay_or_close(self):
  x=self.make();x.commit()
  with patch.object(x,'_capture',side_effect=RuntimeError('disposable lost reverse ACK')):
   with self.assertRaises(RuntimeError):x.reverse()
  self.assertEqual(x.phase,'reverse-uncertain');self.assertEqual(self.observe(),x.before);self.assertFalse(x.closed)
  with self.assertRaises(ValueError):x.reverse()
 def test_WAL_foreign_connection_retains_companions_no_close_ACK(self):
  import sqlite3
  x=self.make();x.commit();other=sqlite3.connect(x.db);other.execute('SELECT ID FROM BOOK LIMIT 1').fetchall();self.addCleanup(other.close)
  # The other reader may set a readmark: no expected-pair refresh is allowed.
  with self.assertRaises(ValueError):self.owned_close(x)
  self.assertFalse(x.closed);self.assertFalse(x.binding['publication_acceptance'])
 def test_WAL_final_observer_claim_absence_kept(self):
  x=self.make();x.commit();absent=self.fixture.c.fixture.root/'missing-native-claim'
  real=self.batch.native_sql_controls
  def changed(reader):
   value=real(reader)
   if self.start.wal_phase.phase=='closed':absent.write_bytes(b'foreign')
   return ({absent:None},value[1])
  self.batch.native_sql_controls=changed
  with self.assertRaises(ValueError):self.owned_close(x)
  self.assertFalse(x.closed);self.assertTrue(absent.exists())

if __name__=='__main__':unittest.main()
