"""Real catalog/reader/FD rollback; explicit fixture SDK origins are not installation."""
import os
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import unittest
from unittest.mock import patch
import test_publication_archive_adoption as f
from test_publication_archive_adoption import o,a,r,load
rollback=load('publication_archive_rollback')

class Controls(unittest.TestCase):
 setUp=f.Tests.setUp
 lease=f.Tests.lease
 cap=f.Tests.cap
 def reversed(self):
  cap=self.cap();cap.install();cap.reverse();return cap
 def consumer(self,cap):
  with patch.object(rollback,'installed'):return rollback.from_reversed(cap)
 def verify(self,cap):
  v=load('publication_archive_verifier');baseline=cap.journal/'baseline.json';real=self.life.vectors
  def bound():
   files,nodes,absent=real();files[baseline]=o.signature(baseline);return files,nodes,tuple(absent)
  with patch.object(v,'installed'),patch.object(self.life,'vectors',bound):return v.verify_rollback_existing(self.c.controller,self.c.writer,self.life,baseline,self.scratch)
 def test_forward_reverse_clear_independent_original_tables(self):
  cap=self.reversed();result=self.consumer(cap).clear();self.assertTrue(result['rollback_verified']);self.assertFalse(result['repair_accepted']);self.assertFalse(result['native_archive_installed']);self.assertEqual(self.c.source.read_bytes(),self.original)
  self.assertFalse((self.c.writer.root/a.PENDING).exists());self.assertFalse((self.c.writer.root/a.TERMINAL).exists())
  result=self.verify(cap);self.assertTrue(result['native_preimage_restored']);self.assertTrue(result['reader_reference_preservation']);self.assertFalse(result['ordinary_import_grant'])
 def test_no_receipt_constructor(self):
  for value in (True,{},object()):
   with patch.object(rollback,'installed'),self.assertRaises(o.Held):rollback.from_reversed(value)
 def test_prepared_or_installed_not_reversed(self):
  cap=self.cap()
  with patch.object(rollback,'installed'),self.assertRaises(o.Held):rollback.from_reversed(cap)
  cap.install()
  with patch.object(rollback,'installed'),self.assertRaises(o.Held):rollback.from_reversed(cap)
 def test_source_changed_keeps_original_pending(self):
  cap=self.reversed();consumer=self.consumer(cap);self.c.source.write_bytes(b'foreign')
  with self.assertRaises(o.Held):consumer.clear()
  self.assertTrue((self.c.writer.root/a.PENDING).exists())
 def test_reader_unrelated_cell_keeps_pending(self):
  cap=self.reversed();consumer=self.consumer(cap)
  with sqlite3.connect(self.life.main) as db:db.execute('UPDATE refs SET PAGE=99')
  with self.assertRaises(o.Held):consumer.clear()
  self.assertTrue((self.c.writer.root/a.PENDING).exists())
 def test_native_full_preimage_changed_holds(self):
  cap=self.reversed();consumer=self.consumer(cap)
  with sqlite3.connect(self.c.controller.native_database) as db:db.execute("UPDATE issues SET ComicSize='foreign'")
  with self.assertRaises(o.Held):consumer.clear()
 def test_late_last_direct_reader_drift_retains_successor(self):
  cap=self.reversed();consumer=self.consumer(cap);real=a.direct;fired=[]
  import inspect
  def late(*args):
   real(*args)
   if cap._phase=='rollback-complete' and any(frame.function=='binding' for frame in inspect.stack()[1:4]) and not fired:
    self.life.main.chmod(0o640);fired.append(True)
  with patch.object(a,'direct',late),self.assertRaises(o.Held):consumer.clear()
  self.assertTrue(fired);self.assertTrue((self.c.writer.root/a.TERMINAL).exists());self.assertEqual(cap._phase,'uncertain')
 def assert_initial_write_unknown(self,name):
  cap=self.reversed();consumer=self.consumer(cap);pending=self.c.writer.root/a.PENDING;terminal=self.c.writer.root/a.TERMINAL
  original_pending=(pending.read_bytes(),o.signature(pending));original_files={path:list(value) for path,value in cap._files.items()};real=o.write;fired=[]
  def lost(path,*args):
   result=real(path,*args)
   if path.name==name:fired.append(True);raise OSError('fixture durable write lost ACK')
   return result
  with patch.object(o,'write',lost),self.assertRaisesRegex(o.Held,'rollback-successor-unknown'):consumer.clear()
  self.assertTrue(fired);self.assertEqual(cap._phase,'uncertain');self.assertEqual((pending.read_bytes(),o.signature(pending)),original_pending);self.assertTrue(terminal.exists())
  for path,value in original_files.items():self.assertEqual(cap._files[path],value)
  if name=='rollback-complete-intent.json':self.assertTrue((cap.journal/name).exists())
  self.assertFalse((cap.journal/'rollback-complete.json').exists())
  with self.assertRaises(o.Held):consumer.clear()
  self.assertEqual(cap._phase,'uncertain');self.assertTrue(pending.exists());self.assertTrue(terminal.exists())
 def test_initial_terminal_write_lost_ack_enters_uncertain(self):self.assert_initial_write_unknown(a.TERMINAL)
 def test_initial_rollback_intent_write_lost_ack_enters_uncertain(self):self.assert_initial_write_unknown('rollback-complete-intent.json')
 def test_pending_unlink_lost_ack_retains_successor(self):
  cap=self.reversed();consumer=self.consumer(cap);real=os.unlink;fired=[]
  def lost(name,*args,**kwargs):
   result=real(name,*args,**kwargs)
   if str(name)==a.PENDING:fired.append(True);raise OSError('fixture lost ACK')
   return result
  with patch.object(os,'unlink',lost),self.assertRaisesRegex(o.Held,'pending-unknown'):consumer.clear()
  self.assertTrue(fired);self.assertTrue((self.c.writer.root/a.TERMINAL).exists());self.assertEqual(cap._phase,'uncertain')
 def test_terminal_unlink_lost_ack_restores_successor(self):
  cap=self.reversed();consumer=self.consumer(cap);real=os.unlink;fired=[]
  def lost(name,*args,**kwargs):
   result=real(name,*args,**kwargs)
   if str(name)==a.TERMINAL:fired.append(True);raise OSError('fixture lost ACK')
   return result
  with patch.object(os,'unlink',lost),self.assertRaisesRegex(o.Held,'terminal-unknown'):consumer.clear()
  self.assertTrue(fired);self.assertTrue((self.c.writer.root/a.TERMINAL).exists());self.assertEqual(cap._phase,'uncertain')
 def test_unknown_journal_never_terminal(self):
  cap=self.reversed();consumer=self.consumer(cap);(cap.journal/'foreign.json').write_bytes(b'{}')
  with self.assertRaises(o.Held):consumer.clear()
 def test_no_clear_replay(self):
  cap=self.reversed();consumer=self.consumer(cap);consumer.clear()
  with self.assertRaises(o.Held):consumer.clear()
 def test_rollback_verifier_requires_exact_original_bytes(self):
  cap=self.reversed();self.consumer(cap).clear();self.c.source.write_bytes(b'x'+self.original[1:])
  with self.assertRaises(o.Held):self.verify(cap)
 def test_rollback_verifier_requires_original_native_tables(self):
  cap=self.reversed();self.consumer(cap).clear()
  with sqlite3.connect(self.c.controller.native_database) as db:db.execute("UPDATE issues SET ComicSize='9999'")
  with self.assertRaises(o.Held):self.verify(cap)
 def test_rollback_verifier_rejects_success_journal_layout(self):
  cap=self.cap();cap.install();cap.complete()
  with self.assertRaises(o.Held):self.verify(cap)
 def test_rollback_verifier_partial_receipt_not_completion(self):
  cap=self.reversed();self.consumer(cap).clear();(cap.journal/'rollback-complete.json').unlink()
  with self.assertRaises(o.Held):self.verify(cap)
 def test_rollback_verifier_marker_reappearance_holds(self):
  cap=self.reversed();self.consumer(cap).clear();(self.c.writer.root/a.TERMINAL).write_bytes(b'{}')
  with self.assertRaises((o.Held,self.c.modules[2].Unavailable)):self.verify(cap)
 def test_late_pending_fd_reader_drift_prevents_unlink(self):
  from contextlib import contextmanager
  cap=self.reversed();consumer=self.consumer(cap);real=o.directory_fd;fired=[]
  @contextmanager
  def late(path,*args):
   with real(path,*args) as fd:
    if path==self.c.writer.root and (cap.journal/'rollback-complete-intent.json').exists() and not fired:
     self.life.main.chmod(0o640);fired.append(True)
    yield fd
  with patch.object(o,'directory_fd',late),self.assertRaises(o.Held):consumer.clear()
  self.assertTrue(fired);self.assertTrue((self.c.writer.root/a.PENDING).exists());self.assertTrue((self.c.writer.root/a.TERMINAL).exists())
 def test_independent_last_direct_reader_drift_no_ack(self):
  cap=self.reversed();self.consumer(cap).clear();real=r.direct;fired=[]
  import inspect
  def late(*args):
   real(*args)
   if inspect.stack()[1].function=='_verify' and not fired:
    self.life.main.chmod(0o640);fired.append(True)
  with patch.object(r,'direct',late),self.assertRaises(o.Held):self.verify(cap)
  self.assertTrue(fired)
 def test_independent_original_attributes_changed_no_ack(self):
  cap=self.reversed();self.consumer(cap).clear();self.c.source.chmod(0o640)
  with self.assertRaises(o.Held):self.verify(cap)
 def test_replaced_rollback_module_blocks_clear(self):
  cap=self.reversed();consumer=self.consumer(cap);path=Path(rollback.__file__);original=path.read_bytes()
  # Disposable proposal source only; restore immediately and never touch tracked code.
  real=o.fact
  with patch.object(o,'fact',wraps=real) as wrapped:
   fired=[]
   def changed(p,*args):
    result=real(p,*args)
    if p==path and not fired:
     result=dict(result);result['sha256']='0'*64;fired.append(True)
    return result
   wrapped.side_effect=changed
   with self.assertRaises(o.Held):consumer.clear()
  self.assertTrue(fired);self.assertEqual(path.read_bytes(),original);self.assertTrue((self.c.writer.root/a.PENDING).exists())
 def test_partial_receipt_bytes_are_not_verified(self):
  for name in ('reversed.json','rollback-complete-intent.json','rollback-complete.json'):
   with self.subTest(name=name):
    other=Controls('runTest');other.setUp()
    try:
     cap=other.reversed();other.consumer(cap).clear();(cap.journal/name).write_bytes(b'{}')
     with self.assertRaisesRegex(o.Held,'receipt-join'):other.verify(cap)
    finally:other.doCleanups()
 def test_pending_marker_foreign_collision_preserved(self):
  cap=self.reversed();consumer=self.consumer(cap);p=self.c.writer.root/a.TERMINAL;p.write_bytes(b'foreign')
  with self.assertRaises(o.Held):consumer.clear()
  self.assertEqual(p.read_bytes(),b'foreign');self.assertTrue((self.c.writer.root/a.PENDING).exists())
 def test_rollback_receipt_numeric_type_aliases_refused(self):
  import json
  for field,value in (('version',True),('version',1.0),('reader_reference_preservation',1)):
   with self.subTest(field=field,value=value):
    other=Controls('runTest');other.setUp()
    try:
     cap=other.reversed();other.consumer(cap).clear();path=cap.journal/'rollback-complete.json';receipt=json.loads(path.read_bytes());receipt[field]=value;path.write_bytes(o.compact(receipt))
     with self.assertRaisesRegex(o.Held,'receipt-join'):other.verify(cap)
    finally:other.doCleanups()
 def test_rollback_receipt_foreign_operation_refused(self):
  import json
  cap=self.reversed();self.consumer(cap).clear();path=cap.journal/'rollback-complete.json';receipt=json.loads(path.read_bytes());receipt['operation_id']='foreign';path.write_bytes(o.compact(receipt))
  with self.assertRaisesRegex(o.Held,'receipt-join'):self.verify(cap)
 def test_rollback_receipt_foreign_source_hash_refused(self):
  import json
  cap=self.reversed();self.consumer(cap).clear();path=cap.journal/'rollback-complete-intent.json';receipt=json.loads(path.read_bytes());receipt['source_sha256']='0'*64;path.write_bytes(o.compact(receipt))
  with self.assertRaisesRegex(o.Held,'receipt-join'):self.verify(cap)
 def test_installer_copies_rollback_module_with_changed_adoption(self):
  import tempfile,types
  import patch_publication_guard as installer
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'api.py').write_text("class Api:\n    commands = ['getVersion', 'checkGithub']\n    def _getVersion(self, **kwargs):\n        pass\n")
   processing=types.ModuleType('patch_publication_processing');processing.main=lambda _:None
   with patch.dict(sys.modules,{'patch_publication_processing':processing}):installer.main(root)
   for name in ('publication_archive_adoption.py','publication_archive_verifier.py','publication_archive_rollback.py'):
    self.assertEqual((root/name).read_bytes(),Path(__file__).with_name(name).read_bytes())
if __name__=='__main__':unittest.main()
