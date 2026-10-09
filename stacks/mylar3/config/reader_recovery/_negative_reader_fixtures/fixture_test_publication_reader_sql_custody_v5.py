"""Actual local SQLite own journal and exact5 transition; no operational grant."""
import importlib.util
import inspect
from pathlib import Path
import unittest
from unittest.mock import patch
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load('sql_custody',str(Path(__file__).resolve().parent / 'fixture_publication_reader_sql_custody_v5.py'))
f=load('admission_fixture',str(Path(__file__).resolve().parent / 'fixture_test_comic_komga_stopped_reader_admission_v3.py'))
r=load('reader_phase',str(Path(__file__).resolve().parent / 'fixture_publication_reader_phase_v1.py'))
class Tests(unittest.TestCase):
 def setUp(self):
  self.c=f.AdmissionTests();self.c.setUp();self.addCleanup(self.c.doCleanups);self.a=self.c.admission();self.db=self.c.config/'database.sqlite';self.disk=f.d
  self.before=self.a._observed['database.sqlite'];self.after=self.a._expected['database.sqlite'];self.baseline=m.raw_pair(self.db)
  self.conn=self.disk.connect(self.db);self.addCleanup(self.conn.close);self.conn.execute('BEGIN IMMEDIATE')
 def make(self):return m.SQLWritingCustody(m._KEY,self.conn,self.db,self.disk,self.c.plan,self.before,self.after,self.baseline)
 def test_genuine_delete_journal_owned_after_exact_five_body(self):
  x=self.make();ack=x.apply_body(r.sql_five_transition);x.close_pending();self.assertFalse(ack['commit_performed']);self.assertTrue(self.conn.in_transaction)
  self.assertIn('-journal',x.pending)
 def test_owned_rollback_keeps_all_original_values(self):
  x=self.make();x.apply_body(r.sql_five_transition);x.rollback_owned();self.assertEqual(x.logical(),self.before)
 def test_no_public_commit_grant(self):
  x=self.make();x.apply_body(r.sql_five_transition)
  with self.assertRaisesRegex(m.Held,'handshake'):x.commit()
  self.assertTrue(self.conn.in_transaction)
 def test_private_key_no_boolean(self):
  with self.assertRaises(m.Held):m.SQLWritingCustody(True,self.conn,self.db,self.disk,self.c.plan,self.before,self.after,self.baseline)
 def test_foreign_correct_row_after_body_holds(self):
  x=self.make();x.apply_body(r.sql_five_transition);self.conn.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='correct-0'")
  with self.assertRaises(m.Held):x.close_pending()
 def test_pending_pair_reseal_holds(self):
  x=self.make();x.apply_body(r.sql_five_transition);x.pending={}
  with self.assertRaises(m.Held):x.close_pending()
 def test_late_logical_callback_other_file_change_holds(self):
  x=self.make();x.apply_body(r.sql_five_transition);real=x.logical
  def changed():v=real();(self.c.config/'foreign').write_bytes(b'foreign');return v
  with patch.object(x,'logical',side_effect=changed):
   with self.assertRaises(m.Held):x.close_pending()
 def test_late_logical_callback_journal_change_holds(self):
  x=self.make();x.apply_body(r.sql_five_transition);real=x.logical
  def changed():v=real();Path(str(self.db)+'-journal').write_bytes(b'foreign');return v
  with patch.object(x,'logical',side_effect=changed):
   with self.assertRaises(m.Held):x.close_pending()
 def test_unowned_hot_journal_reader_holds(self):
  x=self.make();x.apply_body(r.sql_five_transition)
  with self.assertRaisesRegex(m.Held,'unowned-reader-journal'):m.raw_pair(self.db)
 def test_changed_mode_before_body_never_calls_SQL(self):
  x=self.make();self.db.chmod(0o640);fired=False
  def body(*a):
   nonlocal fired
   fired=True;return r.sql_five_transition(*a)
  with self.assertRaises(m.Held):x.apply_body(body)
  self.assertFalse(fired);self.assertEqual(x.logical(),self.before);self.assertFalse(Path(str(self.db)+'-journal').exists())
 def test_samebytes_replacement_before_body_never_calls_SQL(self):
  x=self.make();saved=self.db.read_bytes();self.db.rename(self.db.with_suffix('.retained'));self.db.write_bytes(saved);self.db.chmod(0o600);fired=False
  def body(*a):
   nonlocal fired
   fired=True;return r.sql_five_transition(*a)
  with self.assertRaises(m.Held):x.apply_body(body)
  self.assertFalse(fired);self.assertFalse(Path(str(self.db)+'-journal').exists())
 def test_foreign_namespace_before_body_never_calls_SQL(self):
  x=self.make();(self.c.config/'foreign').write_bytes(b'foreign');fired=False
  def body(*a):
   nonlocal fired
   fired=True;return r.sql_five_transition(*a)
  with self.assertRaises(m.Held):x.apply_body(body)
  self.assertFalse(fired);self.assertFalse(Path(str(self.db)+'-journal').exists())
 def test_last_preflight_logical_callback_mode_drift_no_SQL(self):
  x=self.make();real=x.logical;fired=False
  def changed():v=real();self.db.chmod(0o640);return v
  def body(*a):
   nonlocal fired
   fired=True;return r.sql_five_transition(*a)
  with patch.object(x,'logical',side_effect=changed):
   with self.assertRaises(m.Held):x.apply_body(body)
  self.assertFalse(fired);self.assertFalse(Path(str(self.db)+'-journal').exists())
 def test_final_rollback_logical_mode_drift_no_ACK(self):
  x=self.make();x.apply_body(r.sql_five_transition);real=x.logical;calls=0;fired=False
  def changed():
   nonlocal calls,fired
   value=real();calls+=1
   if calls==2:self.db.chmod(0o640);fired=True
   return value
  with patch.object(x,'logical',side_effect=changed):
   with self.assertRaises(m.Held):x.rollback_owned()
  self.assertTrue(fired)
 def test_final_rollback_logical_foreign_child_no_ACK(self):
  x=self.make();x.apply_body(r.sql_five_transition);real=x.logical;calls=0;fired=False
  def changed():
   nonlocal calls,fired
   value=real();calls+=1
   if calls==2:(self.c.config/'foreign').write_bytes(b'foreign');fired=True
   return value
  with patch.object(x,'logical',side_effect=changed):
   with self.assertRaises(m.Held):x.rollback_owned()
  self.assertTrue(fired)
 def test_final_rollback_logical_sql_write_no_ACK(self):
  x=self.make();x.apply_body(r.sql_five_transition);real=x.logical;calls=0;fired=False
  def changed():
   nonlocal calls,fired
   value=real();calls+=1
   if calls==2:self.conn.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='correct-0'");fired=True
   return value
  with patch.object(x,'logical',side_effect=changed):
   with self.assertRaises(m.Held):x.rollback_owned()
  self.assertTrue(fired)
 def test_real_disk_pair_contract_compatible(self):
  self.baseline=self.disk.pair(self.db);x=self.make();x.apply_body(r.sql_five_transition);x.close_pending();self.assertEqual(x.pending['']['xattrs'],self.baseline['']['xattrs'])
 def test_original_xattrs_before_body_drift_no_SQL(self):
  x=self.make();__import__('os').setxattr(self.db,'user.custody',b'foreign');fired=False
  def body(*a):
   nonlocal fired
   fired=True;return r.sql_five_transition(*a)
  with self.assertRaises(m.Held):x.apply_body(body)
  self.assertFalse(fired);self.assertFalse(Path(str(self.db)+'-journal').exists())
 def test_last_missing_journal_callback_mode_drift_no_SQL(self):
  x=self.make();real=m.signature;fired=False;body_called=False
  def changed(p):
   nonlocal fired
   try:return real(p)
   except FileNotFoundError:
    if str(p)==str(self.db)+'-journal' and inspect.currentframe().f_back.f_code.co_name=='_close_before_write':self.db.chmod(0o640);fired=True
    raise
  def body(*a):
   nonlocal body_called
   body_called=True;return r.sql_five_transition(*a)
  with patch.object(m,'signature',new=changed):
   with self.assertRaises(m.Held):x.apply_body(body)
  self.assertTrue(fired);self.assertFalse(body_called);self.assertFalse(Path(str(self.db)+'-journal').exists())
 def test_last_rollback_missing_journal_callback_mode_drift_no_ACK(self):
  x=self.make();x.apply_body(r.sql_five_transition);real=m.signature;fired=False
  def changed(p):
   nonlocal fired
   try:return real(p)
   except FileNotFoundError:
    if str(p)==str(self.db)+'-journal' and inspect.currentframe().f_back.f_code.co_name=='close_passive':self.db.chmod(0o640);fired=True
    raise
  with patch.object(m,'signature',new=changed):
   with self.assertRaises(m.Held):x.rollback_owned()
  self.assertTrue(fired)
 def test_different_database_connection_held(self):
  with self.assertRaises(m.Held):m.SQLWritingCustody(m._KEY,self.conn,self.c.config/'tasks.sqlite',self.disk,self.c.plan,self.before,self.after,self.baseline)
if __name__=='__main__':unittest.main()
