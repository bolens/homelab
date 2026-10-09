"""Real SQLite/Writer/exchange orchestration with explicit host SDK/parent fixtures."""
import copy
from pathlib import Path
import sqlite3
import sys
import types
import tempfile
import unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE/'_archive_repair_fixtures'))
import comic_archive_repair_action as p
import test_publication_archive_adoption as f
rollback=f.load('publication_archive_rollback');verifier=f.load('publication_archive_verifier')

class Flow(unittest.TestCase):
 def setUp(self):
  self.case=f.Tests('runTest');self.case.setUp();self.addCleanup(self.case.doCleanups);c=self.case.c
  self.modules={m.__name__.split('.')[-1]:m for m in c.modules}
  self.modules.update(publication_archive_owned=f.o,publication_archive_reader=f.r,publication_archive_adoption=f.a,publication_archive_rollback=rollback,publication_reader_lifecycle=types.SimpleNamespace(StoppedReaderCustody=f.Stopped),publication_archive_verifier=verifier)
  class FixtureScope:
   def __init__(sl,custody):sl._custody=custody
   def revalidate(sl):self.case.life.revalidate_stopped()
   def controller_writer(sl):return c.controller,c.writer
  self.modules['publication_native_configured_scope']=types.SimpleNamespace(NativeConfiguredScope=FixtureScope)
  self.private=tempfile.TemporaryDirectory(prefix='archive-provider-flow-');self.addCleanup(self.private.cleanup);self.private_root=Path(self.private.name)
  self.case.scratch=self.private_root/'scratch';self.case.scratch.mkdir(mode=0o700)
  self.case.retention=self.private_root/'retention';self.case.retention.mkdir(mode=0o700)
  self.scope=FixtureScope(self.case.life);self.case.life.scratch=self.case.scratch
  # Original backup declarations are fixture-only. Real full table preservation
  # and restored equality are still independently executed by the repair lease.
  self.output=self.private_root/'provider-output';self.output.mkdir(mode=0o700);control=self.private_root/'provider-controls';control.mkdir(mode=0o700)
  self.plan={'owner':copy.deepcopy(c.owner),'operation_id':c.operation_id,'operation':str(self.output),'controls':{}}
  for name in p.ROLES:
   value={'fixture_only':True} if name!='archive_request' else {'version':1,'owner':c.owner,'operation_id':c.operation_id}
   ref=p.write(control/(name+'.json'),value);self.plan['controls'][name]=ref
  scope_ref=p.write(control/'scopes.json',{'version':1,'scratch':str(self.case.scratch),'retention_root':str(self.case.retention)})
  self.plan['archive_scopes']=scope_ref;self.case.life.proofs=dict(self.plan['controls'],archive_scopes=scope_ref);self.case.life.backup_manifest=self.plan['controls']['backup_manifest'];self.case.life.backup_acceptance=self.plan['controls']['backup_acceptance']
  for module,name in ((p,'installed'),(rollback,'installed'),(verifier,'installed')):
   patcher=patch.object(module,name);patcher.start();self.addCleanup(patcher.stop)
 def cap(self):
  return p.prepare_one(self.plan,self.modules,self.case.life,self.scope,self.case.c.controller,self.case.c.writer,self.case.scratch,self.case.retention)
 def test_actual_forward_reader_and_custody(self):
  original=self.case.original;reader={name:(self.case.cfg/name).read_bytes() for name in ('database.sqlite','tasks.sqlite')}
  result,vectors=p.execute_one(self.plan,self.modules,self.case.life,self.scope);p.close_vectors(vectors)
  self.assertEqual(result['outcome'],'observed-forward');self.assertFalse(result['ordinary_import_grant']);self.assertFalse(result['reader_index_acceptance']);self.assertNotEqual(self.case.c.source.read_bytes(),original)
  self.assertEqual(reader,{name:(self.case.cfg/name).read_bytes() for name in reader});self.assertEqual((self.case.retention/('adopt-'+self.case.c.operation_id)/'swap.arc').read_bytes(),original)
  self.assertEqual(set(x.name for x in self.output.iterdir()),{'execution-originals.json'})
 def test_actual_typed_reverse_and_terminal_clear(self):
  cap=self.cap();before=copy.deepcopy(cap._before);cap.install();result,vectors=p.rollback_owned(cap,self.modules);p.close_vectors(vectors)
  self.assertTrue(result['rollback_verified']);self.assertEqual(self.case.c.source.read_bytes(),self.case.original)
  with sqlite3.connect(self.case.c.controller.native_database) as db:self.assertEqual(f.a.snapshot(db,cap.preparation._deadline),before)
  self.assertFalse((self.case.c.writer.root/f.a.PENDING).exists());self.assertFalse((self.case.c.writer.root/f.a.TERMINAL).exists())
 def verify_forward(self):
  result,_=p.execute_one(self.plan,self.modules,self.case.life,self.scope)
  self.plan['execution_originals']=result['originals'];self.case.life.proofs['archive_execution_originals']=result['originals']
  original_vectors=self.case.life.vectors
  def vectors():
   files,nodes,absent=original_vectors();files[Path(result['baseline']['path'])]=result['baseline']['signature9']
   original=p.decode(Path(result['originals']['path']).read_bytes());files[Path(original['preparation']['path'])]=original['preparation']['signature9'];files[Path(original['preparation']['path']).parent]=original['preparation_directory9'];return files,nodes,absent
  self.case.life.vectors=vectors
  return p.verify_one(self.plan,self.modules,self.case.life,self.scope)
 def test_fresh_independent_forward_verifier(self):
  result,vectors=self.verify_forward();p.close_vectors(vectors)
  self.assertEqual(result['outcome'],'observed-forward');self.assertFalse(result['ordinary_import_grant']);self.assertFalse(result['publication_acceptance'])
 def test_original_preparation_bytes_and_stage_incarnation_not_refreshed(self):
  for mode in ('metadata','directory'):
   with self.subTest(mode=mode):
    # Separate fixture operation for each genuine execute and independent verify.
    fixture=Flow('runTest');fixture.setUp()
    try:
     real=fixture.case.life.revalidate_stopped;fired=[]
     def late():
      real()
      if (fixture.output/'execution-originals.json').exists() and not fired:
       original=p.decode((fixture.output/'execution-originals.json').read_bytes());metadata=Path(original['preparation']['path'])
       if mode=='metadata':metadata.write_bytes(b'{"foreign":true}')
       else:
        z=metadata.parent.stat();__import__('os').utime(metadata.parent,ns=(z.st_atime_ns,z.st_mtime_ns+1000000))
       fired.append(True)
     # Run execute fully before installing the verification-only fault.
     result,_=p.execute_one(fixture.plan,fixture.modules,fixture.case.life,fixture.scope)
     fixture.plan['execution_originals']=result['originals'];fixture.case.life.proofs['archive_execution_originals']=result['originals'];original=p.decode(Path(result['originals']['path']).read_bytes());old=fixture.case.life.vectors
     def vectors():
      files,nodes,absent=old();files[Path(result['baseline']['path'])]=result['baseline']['signature9'];files[Path(original['preparation']['path'])]=original['preparation']['signature9'];files[Path(original['preparation']['path']).parent]=original['preparation_directory9'];return files,nodes,absent
     fixture.case.life.vectors=vectors
     with patch.object(fixture.case.life,'revalidate_stopped',side_effect=late),self.assertRaises((p.Held,f.o.Held)):p.verify_one(fixture.plan,fixture.modules,fixture.case.life,fixture.scope)
     self.assertTrue(fired)
    finally:fixture.doCleanups()
 def test_independent_verifier_foreign_reader_change_held(self):
  real=verifier.verify_existing_with_vectors
  def late(*args,**kw):
   result=real(*args,**kw)
   with sqlite3.connect(self.case.life.main) as db:db.execute('UPDATE refs SET PAGE=99')
   return result
  with patch.object(verifier,'verify_existing_with_vectors',side_effect=late),self.assertRaises(p.Held):self.verify_forward()
 def test_lost_complete_ack_no_replay(self):
  real=f.a.RepairAdoption.complete
  def lost(cap):real(cap);raise OSError('fixture lost ACK')
  with patch.object(f.a.RepairAdoption,'complete',lost),self.assertRaises(OSError):p.execute_one(self.plan,self.modules,self.case.life,self.scope)
  self.assertTrue((self.output/'execution-originals.json').exists());self.assertFalse((self.output/'execute-report.json').exists());self.assertNotEqual(self.case.c.source.read_bytes(),self.case.original)
  with self.assertRaises(p.Held):p.execute_one(self.plan,self.modules,self.case.life,self.scope)
 def test_unknown_exchange_ack_retains_marker_and_bytes(self):
  real=f.a.exchange
  def unknown(*args,**kw):real(*args,**kw);raise OSError('fixture exchange ACK unknown')
  with patch.object(f.a,'exchange',unknown),self.assertRaises(f.o.Held):p.execute_one(self.plan,self.modules,self.case.life,self.scope)
  self.assertTrue((self.case.c.writer.root/f.a.PENDING).exists());self.assertEqual((self.case.retention/('adopt-'+self.case.c.operation_id)/'swap.arc').read_bytes(),self.case.original)
 def test_late_preimage_source_change_no_exchange(self):
  real=p.emit
  def late(*args,**kw):out=real(*args,**kw);self.case.c.source.write_bytes(b'foreign');return out
  with patch.object(p,'emit',side_effect=late),self.assertRaises(f.o.Held):p.execute_one(self.plan,self.modules,self.case.life,self.scope)
  self.assertEqual(self.case.c.source.read_bytes(),b'foreign');self.assertFalse((self.case.c.writer.root/f.a.PENDING).exists())
 def test_noncanonical_scope_type_never_constructs_pair(self):
  spy=types.SimpleNamespace(_custody=self.case.life,controller_writer=lambda:(_ for _ in ()).throw(AssertionError('must not call')))
  with self.assertRaises(p.Held):p.exact_pair(self.modules,self.case.life,spy)
 def test_existing_stage_missing_originals_never_reprepared(self):
  self.case.c.prepare();calls=[]
  def existing(controller,writer,owner,operation,custody):
   calls.append((controller,writer,owner,operation,custody));raise f.o.Held('existing-preparation-original-stage-required')
  self.modules['publication_archive_preparation_existing']=types.SimpleNamespace(from_existing=existing)
  with patch.object(f.o,'prepare_existing',side_effect=AssertionError('must not replay')),self.assertRaises(f.o.Held):self.cap()
  self.assertEqual(len(calls),1);self.assertEqual(self.case.c.source.read_bytes(),self.case.original)
 def test_uncertain_cap_not_automatically_reversed(self):
  cap=self.cap();cap._phase='uncertain';cap._seal()
  with self.assertRaises(p.Held):p.rollback_owned(cap,self.modules)
  self.assertEqual(self.case.c.source.read_bytes(),self.case.original)
 def test_foreign_reader_reference_prevents_install(self):
  cap=self.cap()
  with sqlite3.connect(self.case.life.main) as db:db.execute('UPDATE refs SET PAGE=100')
  with self.assertRaises(f.o.Held):cap.install()
  self.assertEqual(self.case.c.source.read_bytes(),self.case.original)
if __name__=='__main__':unittest.main()
