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
 def test_current_target_witness_is_canonical_and_request_bound(self):
  request={'target_sha256':'a'*64}
  self.assertEqual(h._target_witness({'path':'/library/current.cbz','sha256':'a'*64},request),Path('/library/current.cbz'))
  for text in ('relative.cbz','//library/current.cbz','/library/../current.cbz','/','/library//current.cbz','/library/./current.cbz','/library/\x00.cbz'):
   with self.subTest(path=repr(text)),self.assertRaises(ValueError):h._target_witness({'path':text,'sha256':'a'*64},request)
  for value in ({'path':'/library/current.cbz','sha256':'b'*64},{'path':'/library/current.cbz','sha256':'a'*64,'historical_ack':True}):
   with self.assertRaises(ValueError):h._target_witness(value,request)
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.root.chmod(0o700);self.parent=h.five(os.lstat(self.root));self.path=self.root/'out.json'
 def test_exclusive_private_output_actual_fd_readback(self):
  v=h._journal_write(self.path,b'original',self.parent)
  self.assertEqual(h._read(self.path,v),b'original');self.assertEqual(v[5]&0o7777,0o600)
 def test_receipt_modes_match_real_producer_umasks_and_owned_CAS(self):
  from normalize import save
  for mask,mode in ((0o022,0o644),(0o027,0o640),(0o077,0o600)):
   with self.subTest(umask=oct(mask)):
    receipt=self.root/('receipt-'+str(mask)+'.json');previous=os.umask(mask)
    try:save(receipt,{'original':True})
    finally:os.umask(previous)
    original=h.nine(receipt.stat());self.assertEqual(h._receipt_mode(original),mode)
    output=self.root/('cas-'+str(mask));stamp=h._journal_write(output,b'new',self.parent,mode=h._receipt_mode(original))
    self.assertEqual(stamp[5]&0o7777,mode);self.assertEqual(h.nine(receipt.stat()),original)
 def test_receipt_mode_rejects_writable_foreign_owner_and_hardlink(self):
  self.path.write_bytes(b'original');self.path.chmod(0o644);original=list(h.nine(self.path.stat()))
  for index,value in ((5,0o100664),(5,0o100666),(5,0o104644),(6,os.geteuid()+1),(7,os.getegid()+1)):
   frame=list(original);frame[index]=value
   with self.subTest(field=index,value=value),self.assertRaises(ValueError):h._receipt_mode(frame)
  os.link(self.path,self.root/'alias')
  with self.assertRaises(ValueError):h._receipt_mode(h.nine(self.path.stat()))
 def test_receipt_CAS_mode_metadata_is_durable_before_readback(self):
  events=[];real_mode=os.fchmod;real_sync=os.fsync;real_read=os.read
  def mode(fd,value):events.append('mode');return real_mode(fd,value)
  def sync(fd):events.append('sync');return real_sync(fd)
  def read(fd,count):events.append('read');return real_read(fd,count)
  with patch.object(h.os,'fchmod',side_effect=mode),patch.object(h.os,'fsync',side_effect=sync),patch.object(h.os,'read',side_effect=read):
   h._journal_write(self.path,b'new',self.parent,mode=0o644)
  self.assertLess(events.index('mode'),events.index('sync'));self.assertLess(events.index('sync'),events.index('read'))
 def consumed_mechanics(self):
  # Registry-seal mechanics only, not a native result or publication grant.
  action=object.__new__(h.RetainedPackAction)
  core=dict(phase='consumed',pid=os.getpid(),thread=h.threading.get_ident(),deadline=-1.0,authorization=None)
  h._CORES[action]=core;h._TERMINAL_EXPORTS[action]=(core,b'frame',b'workflow',b'catalog',h._terminal_projection(core))
  self.addCleanup(h._CORES.pop,action,None);self.addCleanup(h._TERMINAL_EXPORTS.pop,action,None)
  return action,core
 def test_expired_mutation_admission_does_not_expire_sealed_readonly_terminal(self):
  action,core=self.consumed_mechanics()
  self.assertIs(h.terminal_core(action),core)
  with self.assertRaisesRegex(ValueError,'live-action'):h._core(action,'consumed')
  with self.assertRaisesRegex(ValueError,'live-action'):h._core(action,'prepared')
 def test_readonly_terminal_requires_original_sealed_consumed_state(self):
  action,core=self.consumed_mechanics()
  for key,value in (('phase','prepared'),('deadline',999999999999.0),('pid',-1),('authorization',object())):
   old=core[key];core[key]=value
   with self.subTest(field=key),self.assertRaisesRegex(ValueError,'terminal-export'):h.terminal_core(action)
   core[key]=old
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
  class Foreign:
   def __hash__(self):raise AssertionError('Foreign lookup dispatched')
  for value in (object(),{},[],Foreign()):
   self.assertFalse(h.enabled(value))
   with self.assertRaisesRegex(ValueError,'Retained worker disabled'):h.select(value,'a'*64,'b'*64)
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
