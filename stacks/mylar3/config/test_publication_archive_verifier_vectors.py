"""Genuine local catalogs, reader pairs and exchange; SDK origins explicitly doubled."""
import inspect
import os
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_publication_archive_adoption as f
import test_publication_archive_rollback as rollback

o=f.o;r=f.r

class Controls(unittest.TestCase):
 setUp=f.Tests.setUp
 lease=f.Tests.lease
 cap=f.Tests.cap
 def completed(self,reversed=False):
  cap=self.cap();cap.install()
  if reversed:
   cap.reverse()
   with patch.object(rollback.rollback,'installed'):rollback.rollback.from_reversed(cap).clear()
  else:cap.complete()
  self.op=cap.root;return cap
 def verify(self,reversed=False):
  self.v=f.load('publication_archive_verifier');baseline=self.op/'journal'/'baseline.json';real=self.life.vectors
  def bound():
   files,nodes,absent=real();files[baseline]=o.signature(baseline);return files,nodes,tuple(absent)
  method=self.v.verify_rollback_existing_with_vectors if reversed else self.v.verify_existing_with_vectors
  with patch.object(self.v,'installed'),patch.object(self.life,'vectors',bound):
   return method(self.c.controller,self.c.writer,self.life,baseline,self.scratch)
 def assert_vectors(self,result):
  self.assertEqual(set(result),{'summary','original_vectors'});v=result['original_vectors']
  self.assertEqual(set(v),{'files9','nodes5','absent','namespaces','claims'})
  for p in (self.c.source,self.c.controller.database,self.c.controller.native_database,self.op/'native-before.sqlite',self.op/'journal'/'baseline.json',self.life.main,self.life.tasks,Path(self.prep._binding['custody']['original']['path'])):
   self.assertEqual(tuple(o.signature(p)),v['files9'][str(p)])
  for p in (self.op,self.op/'journal',self.c.source.parent,self.c.controller.root,self.c.writer.root,self.life.config_root,self.life.restore_root):self.assertIn(str(p),v['nodes5']);self.assertEqual(tuple(sorted(os.listdir(p))),v['namespaces'][str(p)])
  for p in (self.c.writer.root/f.a.PENDING,self.c.writer.root/f.a.TERMINAL,Path(str(self.life.main)+'-wal')):self.assertIn(str(p),v['absent'])
  self.assertFalse(result['summary']['mutation_authority']);self.assertFalse(result['summary']['publication_acceptance']);self.assertFalse(result['summary']['reader_index_acceptance']);self.assertFalse(result['summary']['ordinary_import_grant'])
 def test_forward_complete_vectors_original_facts(self):
  self.completed();self.assert_vectors(self.verify())
 def test_rollback_complete_vectors_original_facts(self):
  self.completed(True);result=self.verify(True);self.assert_vectors(result);self.assertTrue(result['summary']['rollback_verified'])
 def test_absent_inactive_claim_carried(self):
  with sqlite3.connect(self.c.controller.native_database) as db:db.execute("INSERT INTO issues VALUES ('777','456','late.cbz','Wanted','0')")
  self.completed();self.assertIsNone(self.verify()['original_vectors']['claims'][str(self.c.library/'late.cbz')])
 def late_direct(self,action):
  original=r.direct;fired=[]
  def late(*args):
   original(*args)
   if inspect.stack()[1].function=='_verify':
    fired.append(True)
    if len(fired)==2:action(args)
  with patch.object(r,'direct',late),self.assertRaises(o.Held):self.verify()
  self.assertEqual(len(fired),2)
 def test_last_direct_foreign_namespace_holds(self):
  self.completed();self.late_direct(lambda _: (self.c.source.parent/'foreign-extra').write_bytes(b'foreign'))
 def test_last_direct_original_reader_mode_holds(self):
  self.completed();self.late_direct(lambda _: self.life.main.chmod(0o640))
 def test_last_direct_cannot_refresh_passed_file_dictionary(self):
  self.completed()
  def changed(args):
   self.life.main.chmod(0o640);args[0][self.life.main]=o.signature(self.life.main)
  self.late_direct(changed)
 def test_last_direct_declared_absent_claim_holds(self):
  with sqlite3.connect(self.c.controller.native_database) as db:db.execute("INSERT INTO issues VALUES ('777','456','late.cbz','Wanted','0')")
  self.completed();self.late_direct(lambda _: (self.c.library/'late.cbz').symlink_to(self.c.source))
 def test_returned_vectors_are_detached_from_later_state(self):
  self.completed();result=self.verify();original=result['original_vectors']['files9'][str(self.life.main)];self.life.main.chmod(0o640)
  self.assertEqual(result['original_vectors']['files9'][str(self.life.main)],original);self.assertNotEqual(tuple(o.signature(self.life.main)),original)

 def other_owner(self,reversed=False):
  setup=f.native.Controls.setUp
  def two_owner(value):
   setup(value);value.other,value.inventory=value.register_two()
  self.doCleanups()
  with patch.object(f.native.Controls,'setUp',two_owner):self.setUp()
  with patch.object(self.c.modules[2],'inventory',side_effect=self.c.inventory):self.completed(reversed)
  return reversed
 def test_forward_other_owner_full9_and_ancestors_carried(self):
  self.other_owner()
  with patch.object(self.c.modules[2],'inventory',side_effect=self.c.inventory):result=self.verify()
  self.assertEqual(result['original_vectors']['files9'][str(self.c.other)],tuple(o.signature(self.c.other)))
  self.assertIn(str(self.c.other.parent),result['original_vectors']['nodes5'])
 def test_rollback_other_owner_full9_and_ancestors_carried(self):
  self.other_owner(True)
  with patch.object(self.c.modules[2],'inventory',side_effect=self.c.inventory):result=self.verify(True)
  self.assertEqual(result['original_vectors']['files9'][str(self.c.other)],tuple(o.signature(self.c.other)))
  self.assertIn(str(self.c.other.parent),result['original_vectors']['nodes5'])
 def other_owner_late_mutation(self,reversed):
  self.other_owner(reversed);original=r.direct;fired=[];before=o.signature(self.c.other)
  def late(*args):
   original(*args)
   if inspect.stack()[1].function=='_verify':
    fired.append(True)
    if len(fired)==2:self.c.other.write_bytes(b'FOREIGN CONTENT IN SAME INODE')
  with patch.object(self.c.modules[2],'inventory',side_effect=self.c.inventory),patch.object(r,'direct',late),self.assertRaises(o.Held):self.verify(reversed)
  self.assertEqual(len(fired),2);self.assertEqual(o.signature(self.c.other)[:2],before[:2])
 def test_forward_late_other_owner_same_inode_content_holds(self):self.other_owner_late_mutation(False)
 def test_rollback_late_other_owner_same_inode_content_holds(self):self.other_owner_late_mutation(True)

if __name__=='__main__':unittest.main()
