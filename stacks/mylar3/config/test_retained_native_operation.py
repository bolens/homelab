"""Actual public Writer/Controller/bootstrap/catalog/producer fixtures.
Host SDK import identity aliases explicit; installed canonical harness separate.
"""
import importlib.util
import json
import sqlite3
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import test_publication_retained_finalize as fixture

class Controls(unittest.TestCase):
 def setUp(self):
  self.c=fixture.Finalize('runTest');self.c.setUp();self.addCleanup(self.c.doCleanups)
  base=self.c.case;pkg=sys.modules['mylar'];pkg.DATA_DIR=str(self.c.c.root);pkg.CONFIG.DESTINATION_DIR=str(base.case.library)
  for name,module in [('publication_api',fixture.fixture.api),('publication_guard',fixture.fixture.g),('media_writer',fixture.fixture.writers),('workflow_store',fixture.workflow_store)]:
   context=patch.dict(sys.modules,{'mylar.'+name:module});context.start();self.addCleanup(context.stop)
  spec=importlib.util.spec_from_file_location('mylar.native_writers',Path(__file__).with_name('native_writers.py'));self.n=importlib.util.module_from_spec(spec)
  context=patch.dict(sys.modules,{spec.name:self.n});context.start();self.addCleanup(context.stop);spec.loader.exec_module(self.n)
  context=patch.object(pkg,'native_writers',self.n,create=True);context.start();self.addCleanup(context.stop)
  spec=importlib.util.spec_from_file_location('mylar.publication_native',Path(__file__).with_name('publication_native.py'));self.native=importlib.util.module_from_spec(spec)
  context=patch.dict(sys.modules,{spec.name:self.native});context.start();self.addCleanup(context.stop);spec.loader.exec_module(self.native)
  # Host backend locator only: match the same real default used by the installed /opt runtime.
  context=patch.dict(fixture.fixture.api.Controller.__init__.__kwdefaults__,{'tool_root':fixture.fixture.g.TOOL_ROOT});context.start();self.addCleanup(context.stop)
  self.n.initialize_publication()
  with self.n.operation(startup=True) as writer:self.n.startup_catalog(writer);self.n.complete_startup()
 def raw(self):return json.dumps(self.c.body)
 def test_native_accept_and_passive_wrappers_use_real_ordinary_writer(self):
  source=self.c.case.original.read_bytes();target=self.c.case.target.read_bytes()
  answer=self.native.accept_retained_delivery(self.raw())
  status=self.native.retained_delivery_status(self.raw());self.assertEqual(answer['outcome'],status['outcome'])
  self.assertEqual(self.native.retained_delivery_status(self.raw(),answer['ack']),status)
  self.assertEqual(self.c.case.original.read_bytes(),source);self.assertEqual(self.c.case.target.read_bytes(),target)
 def test_native_finalize_and_passive_wrappers_complete_exact_member(self):
  answer=self.native.finalize_retained_delivery(self.raw());self.assertEqual(answer,self.native.retained_finalization_status(self.raw()))
  self.assertEqual(answer['outcome'],'fresh-retained-backend-finalized');self.assertFalse(answer['ordinary_import_grant']);self.assertFalse(answer['cleanup_grant'])
  with self.assertRaises((fixture.o.Held,FileExistsError)):self.native.finalize_retained_delivery(self.raw())
 def test_native_annual_finalize_preserves_distinct_release_and_status(self):
  with sqlite3.connect(self.c.c.native_database) as db:
   db.execute('DELETE FROM issues');db.execute('INSERT INTO annuals VALUES(?,?,?,?,?,?)',('123','456','789',self.c.case.target.name,'Archived',0))
  self.c.body['owner']={'table':'annuals','issueid':'123','parentcomicid':'456','releasecomicid':'789'}
  pack=self.c.store.get('pack',self.c.body['pack_id']);pack['members'][0].update(kind='annual',releasecomicid='789');self.c.store.set('pack',self.c.body['pack_id'],pack)
  answer=self.native.finalize_retained_delivery(self.raw());self.assertEqual(answer,self.native.retained_finalization_status(self.raw()))
  with sqlite3.connect(self.c.c.native_database) as db:self.assertEqual(db.execute('SELECT ReleaseComicID,Status FROM annuals').fetchall(),[('789','Archived')])
  wrong=dict(self.c.body,owner=dict(self.c.body['owner'],releasecomicid='790'))
  with self.assertRaises(fixture.o.Held):self.native.retained_finalization_status(json.dumps(wrong))
 def test_default_recovery_operation_flags_unchanged(self):
  with self.n.operation() as writer:self.assertTrue(all(getattr(writer.local[1],k) for k in ('allow_pending','allow_tagger_pending','allow_release_pending')))
 def test_default_legacy_operation_flags_unchanged(self):
  self.n._PUBLICATION=False
  with self.n.operation() as writer:
   self.assertFalse(writer.local[1].allow_pending);self.assertTrue(writer.local[1].allow_tagger_pending);self.assertTrue(writer.local[1].allow_release_pending)
 def test_ordinary_outer_and_nested_hold_all_false(self):
  with self.n.operation(ordinary=True) as writer:
   self.assertTrue(self.n.active());self.assertFalse(any(getattr(writer.local[1],k) for k in ('allow_pending','allow_tagger_pending','allow_release_pending')))
   with self.n.operation(ordinary=True) as nested:self.assertIs(nested.local,writer.local);self.assertFalse(any(getattr(nested.local[1],k) for k in ('allow_pending','allow_tagger_pending','allow_release_pending')))
  self.assertFalse(self.n.active())
 def test_inherited_recovery_cannot_narrow_purpose_or_call_producer(self):
  with self.n.operation() as writer:
   before=(writer.local[1].depth,writer.local[1].allow_pending,writer.local[1].allow_tagger_pending,writer.local[1].allow_release_pending)
   with self.assertRaisesRegex(fixture.fixture.g.Unavailable,'Inherited recovery purpose'):self.native.accept_retained_delivery(self.raw())
   self.assertEqual((writer.local[1].depth,writer.local[1].allow_pending,writer.local[1].allow_tagger_pending,writer.local[1].allow_release_pending),before)
  self.assertFalse((self.c.c.root/fixture.r.NAME).exists())
 def test_ordinary_cannot_gain_default_recovery_purpose_by_nesting(self):
  with self.n.operation(ordinary=True):
   with self.assertRaisesRegex(ValueError,'Nested writer cannot gain recovery authority'):
    with self.n.operation():pass
 def test_invalid_startup_reconcile_and_nonbool_purposes(self):
  for kwargs in ({'ordinary':1},{'ordinary':True,'startup':True},{'ordinary':True,'reconcile':True}):
   with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
    with self.n.operation(**kwargs):pass
 def test_ordinary_uninitialized_startup_remains_held(self):
  self.n._STARTUP_COMPLETE=False
  with self.assertRaisesRegex(fixture.fixture.g.Unavailable,'requires restart'):
   with self.n.operation(ordinary=True):pass
 def test_legacy_mode_cannot_enter_explicit_ordinary_scope(self):
  self.n._PUBLICATION=False
  with self.assertRaisesRegex(fixture.fixture.g.Unavailable,'requires publication mode'):
   with self.n.operation(ordinary=True):pass
 def test_pending_markers_remain_held_before_any_producer(self):
  writer=self.n.owner();real=writer.__class__.hold
  def bounded(self,**kwargs):return real(self,**dict(kwargs,timeout=0))
  for name in ('normalizer-v1.pending','tagger-v2.pending','release-v1.pending'):
   path=writer.root/name;path.write_bytes(b'mylar-media-writer-v1\n');path.chmod(0o600)
   try:
    with patch.object(writer.__class__,'hold',bounded),self.assertRaises(fixture.fixture.writers.Busy):self.native.accept_retained_delivery(self.raw())
   finally:path.unlink()
  self.assertFalse((self.c.c.root/fixture.r.NAME).exists())
 def test_negative_correction_markers_never_enter_ordinary_body(self):
  writer=self.n.owner()
  for name in ('negative-retirement-v1.pending','negative-retirement-v1.terminal-pending','archive-repair-v1.pending','archive-repair-v1.terminal-pending'):
   path=writer.root/name;path.write_bytes(b'foreign')
   try:
    with self.assertRaises(fixture.fixture.writers.Busy):
     with self.n.operation(ordinary=True):self.fail('negative phase admitted')
   finally:path.unlink()
  self.assertEqual(self.n._OPERATIONS,0);self.assertFalse(self.n.active())
 def test_exception_cleanup_restores_scope_without_new_purpose(self):
  with self.assertRaisesRegex(OSError,'literal failure'):
   with self.n.operation(ordinary=True):raise OSError('literal failure')
  writer=self.n.owner();self.assertEqual(writer.local[1].depth,0);self.assertEqual(self.n._OPERATIONS,0);self.assertFalse(self.n.active())
  self.assertFalse(any(getattr(writer.local[1],name,False) for name in ('allow_pending','allow_tagger_pending','allow_release_pending')))
 def test_before_and_after_actual_admission_called_and_postchange_held(self):
  real=self.n.admission;calls=[]
  def admit(writer,**kwargs):calls.append((writer.local[1].depth,writer.local[1].allow_pending,writer.local[1].allow_tagger_pending,writer.local[1].allow_release_pending));return real(writer,**kwargs)
  with patch.object(self.n,'admission',admit):
   with self.n.operation(ordinary=True):pass
  self.assertEqual(len(calls),2);self.assertTrue(all(depth>0 and flags==(False,False,False) for depth,*tail in calls for flags in [tuple(tail)]))
  path=self.c.writer.root/'tagger-publication-v1.json'
  try:
   with self.assertRaises(fixture.fixture.g.Unavailable):
    with self.n.operation(ordinary=True):path.write_bytes(b'foreign')
  finally:path.unlink()
 def test_default_disabled_wrapper_checks_preserved(self):
  with patch.object(fixture.r,'ENABLED',False),self.assertRaisesRegex(ValueError,'not activated'):self.native.accept_retained_delivery(self.raw())
  with patch.object(fixture.f,'ENABLED',False),self.assertRaisesRegex(ValueError,'disabled'):self.native.finalize_retained_delivery(self.raw())

if __name__=='__main__':unittest.main()
