"""Real local SQL/FD mechanics; no fabricated native/HTTP capability positive."""
from contextlib import closing
import copy
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import retained_pack_handoff as h

class Mechanics(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.root.chmod(0o700);self.parent=h.five(os.lstat(self.root));self.path=self.root/'out.json'
 def test_exclusive_private_output_actual_fd_readback(self):
  v=h._journal_write(self.path,b'original',self.parent)
  self.assertEqual(h._read(self.path,v),b'original');self.assertEqual(v[5]&0o7777,0o600)
 def test_created_fd_first_fsync_mode_drift_refuses(self):
  real=os.fsync;fired=[]
  def late(fd):
   real(fd)
   if os.fstat(fd).st_mode&0o170000==0o100000:os.fchmod(fd,0o640);fired.append(True)
  with patch.object(h.os,'fsync',side_effect=late),self.assertRaises(ValueError):h._journal_write(self.path,b'original',self.parent)
  self.assertTrue(fired)
 def test_output_directory_replacement_no_foreign_write(self):
  old=self.root.with_name(self.root.name+'-kept');self.root.rename(old);self.root.mkdir(mode=0o700)
  try:
   with self.assertRaises(ValueError):h._journal_write(self.path,b'foreign',self.parent)
   self.assertFalse(self.path.exists())
  finally:self.root.rmdir();old.rename(self.root)
 def test_duplicate_output_never_overwritten(self):
  self.path.write_bytes(b'foreign')
  with self.assertRaises(FileExistsError):h._journal_write(self.path,b'original',self.parent)
  self.assertEqual(self.path.read_bytes(),b'foreign')
 def test_original_replaced_same_bytes_refuses(self):
  self.path.write_bytes(b'old');v=h.nine(os.lstat(self.path));self.path.rename(self.root/'old');self.path.write_bytes(b'old')
  with self.assertRaises(ValueError):h._read(self.path,v)
 def test_complete_original_tree_refuses_late_child(self):
  self.path.write_bytes(b'old');f=h._capture([],trees=[self.root]);(self.root/'foreign').write_bytes(b'foreign')
  with self.assertRaises(ValueError):h._raw(f)
 def test_claim_absence_refuses_actual_shadow(self):
  f=h._capture([]);f['claims'][str(self.path)]=None;self.path.symlink_to(self.root)
  with self.assertRaises(ValueError):h._raw(f)
 def test_original_xattrs_preserved_and_changed_refused(self):
  self.path.write_bytes(b'old');os.setxattr(self.path,'user.fixture',b'original');f=h._capture([self.path])
  out=self.root/'second';h._journal_write(out,b'new',self.parent,f['attrs'][str(self.path)])
  self.assertEqual(os.getxattr(out,'user.fixture'),b'original')
  os.setxattr(self.path,'user.fixture',b'foreign')
  with self.assertRaises(ValueError):h._raw(f)
 def test_sql_exact_types_and_unrelated_tables(self):
  db=self.root/'db.sqlite'
  with closing(sqlite3.connect(db)) as c:c.executescript('CREATE TABLE a(k TEXT,v BLOB);CREATE TABLE untouched(x INTEGER);');c.execute('INSERT INTO a VALUES (?,?)',('key',b'payload'));c.execute('INSERT INTO untouched VALUES (7)');c.commit()
  v=h.nine(os.lstat(db));got=h._sql(db,v)
  self.assertEqual(got['rows']['a'],['["key",{"blob":"7061796c6f6164"}]']);self.assertEqual(got['rows']['untouched'],['[7]'])
 def test_sql_original_mode_before_connect_refuses(self):
  db=self.root/'db.sqlite'
  with closing(sqlite3.connect(db)) as c:c.execute('CREATE TABLE a(k TEXT)');c.commit()
  v=h.nine(os.lstat(db));db.chmod(0o640)
  with patch.object(h.sqlite3,'connect') as connect,self.assertRaises(ValueError):h._sql(db,v)
  connect.assert_not_called()
 def test_no_saved_json_or_arbitrary_object_factory(self):
  with self.assertRaises(ValueError):h.RetainedPackAction()
  with self.assertRaises(ValueError):h.dispatch(object())
  with self.assertRaises(ValueError):h.consume(object())
 def test_default_disabled_selection(self):
  with self.assertRaises(ValueError):h.select(object(),'a'*64,'b'*64)
 def test_missing_installed_api_pin_is_explicit(self):
  self.assertIsNone(h.NATIVE_API_SHA);self.assertFalse(h.ENABLED)
 def test_remote_raw_transport_exact_finite_schema_source(self):
  import inspect
  source=inspect.getsource(h.Maintenance.retained_pack_return)
  self.assertIn("('retainedDeliveryFinalize','retainedDeliveryStatus')",source);self.assertIn('remote_unlocked(self.worker)',source);self.assertIn('text=True,limit=4*1024*1024',source)
 def test_original_vectors_detached_from_mutable_helper(self):
  self.path.write_bytes(b'old');f=h._capture([self.path]);original=copy.deepcopy(f)
  clone=h._detached(f);clone['files'][str(self.path)][5]=0
  self.assertEqual(f,original)
 def test_known_control_original_precedes_first_tree_callback(self):
  self.path.write_bytes(b'original');self.path.chmod(0o600);tree=self.root/'tree';tree.mkdir()
  real=os.listdir;fired=[]
  def late(p):
   names=real(p)
   if Path(p)==tree and not fired:self.path.chmod(0o640);fired.append(True)
   return names
  with patch.object(h.os,'listdir',side_effect=late),patch.object(h,'_read') as stream,self.assertRaises(ValueError):
   h._capture([self.path],trees=[tree])
  self.assertTrue(fired);stream.assert_not_called()
 def test_known_ancestor_original_precedes_first_tree_callback(self):
  self.path.write_bytes(b'original');tree=self.root/'tree';tree.mkdir();real=os.listdir;fired=[]
  def late(p):
   names=real(p)
   if Path(p)==tree and not fired:self.root.chmod(0o750);fired.append(True)
   return names
  with patch.object(h.os,'listdir',side_effect=late),self.assertRaises(ValueError):h._capture([self.path],trees=[tree])
  self.assertTrue(fired)
 def test_unrelated_33GiB_has_raw_fact_without_content_or_xattrs(self):
  self.path.write_bytes(b'original');large=self.root/'unrelated.cbz'
  with large.open('wb') as f:f.truncate(33*1024**3)
  original=h.nine(large.lstat());real=h._read;real_attrs=os.listxattr;calls=[];attrs=[]
  def read(p,*a,**k):calls.append(str(p));return real(p,*a,**k)
  def xattrs(p,*a,**k):attrs.append(str(p));return real_attrs(p,*a,**k)
  with patch.object(h,'_read',side_effect=read),patch.object(h.os,'listxattr',side_effect=xattrs):
   frame=h._capture([self.path],trees=[self.root])
  self.assertEqual(tuple(frame['files'][str(large)]),original)
  self.assertEqual(calls,[str(self.path)]);self.assertNotIn(str(large),attrs)
  self.assertNotIn(str(large),frame['hashes']);self.assertNotIn(str(large),frame['attrs'])
  large.chmod(0o640)
  with self.assertRaises(ValueError):h._raw(frame)
 def test_unrelated_hardlink_symlink_and_fifo_keep_raw_originals(self):
  self.path.write_bytes(b'original');foreign=self.root/'foreign';foreign.write_bytes(b'foreign')
  hard=self.root/'hard';os.link(foreign,hard);link=self.root/'link';link.symlink_to(foreign);fifo=self.root/'fifo';os.mkfifo(fifo)
  frame=h._capture([self.path],trees=[self.root])
  for p in (foreign,hard,link,fifo):
   self.assertEqual(tuple(frame['files'][str(p)]),h.nine(p.lstat()));self.assertNotIn(str(p),frame['hashes'])
  link.unlink();link.symlink_to(self.path)
  with self.assertRaises(ValueError):h._raw(frame)
 def test_selected_link_exclusivity_is_not_waived(self):
  self.path.write_bytes(b'original');hard=self.root/'hard';os.link(self.path,hard)
  with self.assertRaises(ValueError):h._capture([self.path],trees=[self.root])
 def test_selected_capture_conflicts_original_before_first_stream(self):
  self.path.write_bytes(b'original');tree=self.root/'tree';tree.mkdir();selected=tree/'selected';selected.write_bytes(b'original')
  originals=h._capture([self.path],trees=[self.root]);selected.chmod(0o640)
  with patch.object(h,'_read') as stream,self.assertRaises(ValueError):
   h._capture([selected],stream_trees=[tree],originals=originals)
  stream.assert_not_called()
 def test_selected_capture_late_rewrite_of_caller_facts_cannot_reseal(self):
  self.path.write_bytes(b'original');tree=self.root/'tree';tree.mkdir();selected=tree/'selected';selected.write_bytes(b'original')
  originals=h._capture([self.path],trees=[self.root]);real=os.listdir;fired=[]
  def late(p):
   names=real(p)
   if Path(p)==tree and not fired:
    selected.chmod(0o640);originals['files'][str(selected)]=h.nine(selected.lstat());fired.append(True)
   return names
  with patch.object(h.os,'listdir',side_effect=late),patch.object(h,'_read') as stream,self.assertRaises(ValueError):
   h._capture([selected],stream_trees=[tree],originals=originals)
  self.assertTrue(fired);stream.assert_not_called()
 def test_exact_transport_global_replacement_refuses(self):
  m=object.__new__(h.Maintenance)
  h._transport(m)
  with patch.dict(h._RETURN.__globals__,request=lambda *a,**k:'saved'):
   with self.assertRaises(ValueError):h._transport(m)
 def test_exact_transport_method_replacement_refuses(self):
  m=object.__new__(h.Maintenance)
  with patch.object(h.Maintenance,'retained_pack_return',lambda *a:b'saved'):
   with self.assertRaises(ValueError):h._transport(m)
 def test_raw_pending_namespace_refuses(self):
  f=h._capture([],absent=[self.path]);self.path.write_bytes(b'pending')
  with self.assertRaises(ValueError):h._raw(f)

if __name__=='__main__':unittest.main()
